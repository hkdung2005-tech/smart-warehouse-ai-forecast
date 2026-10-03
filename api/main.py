"""
Smart Warehouse AI Forecast — FastAPI Application
SCRUM-13: Khung API kết nối PostgreSQL và RabbitMQ.
          Các route nghiệp vụ (POST /jobs, GET /jobs/{id}, DLQ)
          sẽ được Chấn implement theo API contract SCRUM-12.
"""

import os
import logging
from contextlib import asynccontextmanager

import asyncpg
import aio_pika
from fastapi import FastAPI, Request

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("warehouse.api")

# ─────────────────────────────────────────────
# Config từ environment (docker-compose truyền vào)
# ─────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "")

# Tên các queue — đồng bộ với worker/config.py của Bảo
MAIN_QUEUE  = os.getenv("MAIN_QUEUE", "jobs")
DLQ         = os.getenv("DLQ",        "jobs.dlq")
# Retry queues được Worker tự tạo động: jobs.retry.1s, jobs.retry.2s, jobs.retry.4s
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))


# ─────────────────────────────────────────────
# Lifespan: khởi tạo / đóng connection pool
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Mở connection pool khi startup, đóng khi shutdown."""

    # ── PostgreSQL pool ──────────────────────
    logger.info("Connecting to PostgreSQL …")
    app.state.db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("PostgreSQL pool ready ✓")

    # ── RabbitMQ connection ──────────────────
    logger.info("Connecting to RabbitMQ …")
    app.state.rmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
    logger.info("RabbitMQ connection ready ✓")

    # ── Khai báo queue (idempotent) ──────────
    async with app.state.rmq_connection.channel() as ch:
        # DLQ khai báo trước (main queue cần biết tên DLQ)
        await ch.declare_queue(DLQ,        durable=True)
        await ch.declare_queue(MAIN_QUEUE, durable=True)
        # Retry queues do Worker tự declare khi khởi động
        logger.info("Queues declared: %s | DLQ: %s", MAIN_QUEUE, DLQ)

    yield  # ── ứng dụng đang chạy ────────────

    # ── Cleanup ──────────────────────────────
    logger.info("Shutting down …")
    await app.state.rmq_connection.close()
    await app.state.db_pool.close()
    logger.info("Shutdown complete.")


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title="Smart Warehouse AI Forecast API",
    version="0.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# GET /health
# Theo API contract mục 3.1 — trả {"status": "ok"}
# Mở rộng thêm checks để dễ debug môi trường
# ─────────────────────────────────────────────
@app.get("/health", tags=["infra"])
async def health(request: Request):
    """
    Kiểm tra API và các service phụ thuộc còn sống.

    Response luôn 200 (circuit-breaker phía client tự xử lý);
    trường `status` là "ok" khi mọi check đều pass,
    "degraded" khi có check lỗi.
    """
    checks: dict = {}

    # ── PostgreSQL ───────────────────────────
    try:
        async with request.app.state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.error("PostgreSQL health check failed: %s", exc)
        checks["postgres"] = "error"

    # ── RabbitMQ ─────────────────────────────
    try:
        if not request.app.state.rmq_connection.is_closed:
            checks["rabbitmq"] = "ok"
        else:
            checks["rabbitmq"] = "error"
    except Exception as exc:
        logger.error("RabbitMQ health check failed: %s", exc)
        checks["rabbitmq"] = "error"

    overall_status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"

    return {
        "status": overall_status,
        "checks": checks,
        "queues": {
            "main": MAIN_QUEUE,
            "dlq":  DLQ,
        },
    }


# ─────────────────────────────────────────────
# Các route nghiệp vụ — Chấn implement (SCRUM-12)
# ─────────────────────────────────────────────
# POST /jobs       → tạo job, lưu DB, đẩy RabbitMQ
# GET  /jobs/{id}  → tra cứu trạng thái job