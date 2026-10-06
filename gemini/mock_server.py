# Yêu cầu Python >= 3.10 (asyncio.Lock tạo ở module level)
"""
Mock Gemini Server using FastAPI.

Simulates Google Gemini API responses for testing the Smart Warehouse AI Forecast worker,
supporting various error modes, latencies, flaky behavior, and fail_n retry mechanisms.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import random
import re
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
# State & Thread/Async-safe storage
# ─────────────────────────────────────────────────────────────

TAG_PATTERN = re.compile(r"^\[mock:([a-zA-Z0-9_]+)(?::([0-9]+))?\]", re.IGNORECASE)

VALID_MODES = {
    "success",
    "default",
    "slow",
    "429",
    "500",
    "400",
    "timeout",
    "bad_json",
    "not_json",
    "flaky",
    "fail_n",
}


class ServerState:
    """Manages runtime mode and request metrics in a thread-safe manner."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.global_mode: str = os.getenv("MOCK_MODE", "success").lower()
        self.global_fail_n: int = int(os.getenv("MOCK_FAIL_COUNT", "2"))
        self.total_requests: int = 0
        self.requests_by_payload: Dict[str, int] = {}
        self.fail_n_counts: Dict[str, int] = {}

    async def record_generate_request(self, payload: str) -> None:
        """Increments request counters for global and per-payload tracking."""
        async with self.lock:
            self.total_requests += 1
            self.requests_by_payload[payload] = self.requests_by_payload.get(payload, 0) + 1

    async def get_and_increment_fail_n(self, payload: str) -> int:
        """Increments and returns the attempt counter for a specific payload in fail_n mode."""
        async with self.lock:
            count = self.fail_n_counts.get(payload, 0) + 1
            self.fail_n_counts[payload] = count
            return count

    async def set_mode(self, mode: str, n: Optional[int] = None) -> tuple[str, int]:
        """Sets the global simulation mode and optional fail_n threshold."""
        async with self.lock:
            normalized = mode.lower().strip()
            if normalized in ("default", "success"):
                self.global_mode = "success"
            else:
                self.global_mode = normalized

            if n is not None and n > 0:
                self.global_fail_n = n
            return self.global_mode, self.global_fail_n

    async def reset(self) -> None:
        """Clears all statistics and fail_n tracking counters."""
        async with self.lock:
            self.total_requests = 0
            self.requests_by_payload.clear()
            self.fail_n_counts.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Returns snapshot of current statistics."""
        async with self.lock:
            return {
                "total_requests": self.total_requests,
                "distinct_payloads": len(self.requests_by_payload),
                "max_calls_per_payload": max(self.requests_by_payload.values(), default=0),
                "top_payloads": dict(
                    sorted(self.requests_by_payload.items(), key=lambda kv: kv[1], reverse=True)[:20]
                ),
                "global_mode": self.global_mode,
                "global_fail_n": self.global_fail_n,
            }


state = ServerState()
app = FastAPI(title="Mock Gemini Server", version="1.0.0")


# ─────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    payload: str = Field(..., min_length=1, description="Text payload for AI forecast")


class AdminModeRequest(BaseModel):
    mode: str = Field(..., description="Mode name (success, default, 429, 500, 400, slow, timeout, bad_json, not_json, flaky, fail_n)")
    n: Optional[int] = Field(None, description="Failure count threshold for fail_n mode")


# ─────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────


def log_request(mode: str, status_code: int, payload: str) -> None:
    """Logs request summary to stdout with timestamp, applied mode, and status code."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    preview = payload.replace("\n", " ").strip()
    if len(preview) > 60:
        preview = preview[:57] + "..."
    print(f"[{timestamp}] mode={mode} status={status_code} payload=\"{preview}\"", flush=True)


def parse_mode_header(header_val: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Parses X-Mock-Mode header value (e.g. 'fail_n:3' or '429')."""
    if not header_val:
        return None, None
    parts = header_val.strip().split(":", 1)
    mode = parts[0].lower()
    n: Optional[int] = None
    if len(parts) > 1 and parts[1].isdigit():
        n = int(parts[1])
    return mode, n


def resolve_mode(payload: str, header_mode: Optional[str]) -> tuple[str, Optional[int]]:
    """
    Resolves the effective mode and N parameter using priority order:
    1. Payload tag: [mock:<mode>] or [mock:<mode>:<n>]
    2. Header: X-Mock-Mode
    3. Global mode set via POST /admin/mode or env MOCK_MODE
    """
    # 1. Tag in payload
    tag_match = TAG_PATTERN.match(payload)
    if tag_match:
        mode = tag_match.group(1).lower()
        n = int(tag_match.group(2)) if tag_match.group(2) else None
        return mode, n

    # 2. X-Mock-Mode Header
    h_mode, h_n = parse_mode_header(header_mode)
    if h_mode:
        return h_mode, h_n

    # 3. Global mode & Env fallback
    return state.global_mode, None


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@app.get("/health", summary="Health check")
async def health() -> Dict[str, str]:
    """Returns basic health status of the mock server."""
    return {"status": "ok"}


@app.post("/generate", summary="Generate AI forecast mock response")
async def generate(
    req: GenerateRequest,
    x_mock_mode: Optional[str] = Header(None, alias="X-Mock-Mode"),
) -> Response:
    """
    Generates mock response according to resolved mode.
    Handles success, latency, simulated errors, malformed payloads, and fail_n retries.
    """
    payload = req.payload
    await state.record_generate_request(payload)

    mode, parsed_n = resolve_mode(payload, x_mock_mode)
    if mode in ("default", ""):
        mode = "success"

    resp: Response

    if mode == "success":
        preview = payload[:50]
        resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": f"Forecast result for: {preview} [Mock Gemini]"},
        )

    elif mode == "slow":
        delay = float(parsed_n) if parsed_n else float(os.getenv("MOCK_DELAY", "2.0"))
        await asyncio.sleep(delay)
        preview = payload[:50]
        resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": f"Slow forecast result for: {preview} [Mock Gemini]"},
        )

    elif mode == "429":
        resp = Response(content=b"", status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    elif mode == "500":
        resp = Response(content=b"", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif mode == "400":
        resp = Response(content=b"", status_code=status.HTTP_400_BAD_REQUEST)

    elif mode == "timeout":
        # Worker has 60s timeout, sleep 90s to simulate timeout failure
        preview = payload[:50]
        print(
            f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S UTC}] mode=timeout sleeping 90s payload=\"{preview}\"",
            flush=True,
        )
        await asyncio.sleep(90)
        resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"result": f"Delayed forecast result for: {preview} [Mock Gemini]"},
        )

    elif mode == "bad_json":
        # 200 OK but JSON is missing 'result' field or result is not string
        resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"foo": "bar", "status": "missing_result_key"},
        )

    elif mode == "not_json":
        # 200 OK with plain text response
        resp = PlainTextResponse(
            content="Plain text forecast output without JSON wrapper",
            status_code=status.HTTP_200_OK,
        )

    elif mode == "flaky":
        error_rate = float(os.getenv("MOCK_ERROR_RATE", "0.3"))
        if random.random() < error_rate:
            error_status = random.choice([status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_500_INTERNAL_SERVER_ERROR])
            resp = Response(content=b"", status_code=error_status)
        else:
            preview = payload[:50]
            resp = JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"result": f"Flaky success forecast result for: {preview} [Mock Gemini]"},
            )

    elif mode == "fail_n":
        target_n = parsed_n if parsed_n is not None else state.global_fail_n
        attempt = await state.get_and_increment_fail_n(payload)
        if attempt <= target_n:
            resp = Response(content=b"", status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        else:
            preview = payload[:50]
            resp = JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"result": f"Recovered forecast result after {target_n} failures (attempt #{attempt}) for: {preview} [Mock Gemini]"},
            )

    else:
        # Unknown mock mode returns 422
        resp = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": f"Unknown mock mode: {mode}"},
        )

    log_request(mode=mode, status_code=resp.status_code, payload=payload)
    return resp


@app.post("/admin/mode", summary="Update global mock mode")
async def admin_set_mode(req: AdminModeRequest) -> Dict[str, Any]:
    """Updates the global server mode and optional fail_n count during runtime."""
    normalized_mode = req.mode.lower().strip()
    if normalized_mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"Unknown mock mode: {req.mode}")

    new_mode, fail_n = await state.set_mode(req.mode, req.n)
    return {
        "status": "mode_updated",
        "global_mode": new_mode,
        "global_fail_n": fail_n,
    }


@app.get("/admin/stats", summary="Get request statistics")
async def admin_get_stats() -> Dict[str, Any]:
    """Returns request counts and current mode configuration."""
    return await state.get_stats()


@app.post("/admin/reset", summary="Reset request statistics")
async def admin_reset() -> Dict[str, str]:
    """Resets request statistics and fail_n tracking counters."""
    await state.reset()
    return {"status": "reset_successful"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "9000"))
    uvicorn.run("mock_server:app", host="0.0.0.0", port=port, reload=False)
