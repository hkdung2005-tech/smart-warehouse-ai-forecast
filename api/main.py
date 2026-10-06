"""
Smart Warehouse AI Forecast — FastAPI Application
SCRUM-13: Khung API kết nối PostgreSQL và RabbitMQ.
SCRUM-17: POST /jobs lưu job và publish vào RabbitMQ.
"""

import asyncio
import json
import os
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import aio_pika
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, field_validator

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


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


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
    max_rmq_retries = 5
    for attempt in range(1, max_rmq_retries + 1):
        try:
            app.state.rmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
            logger.info("RabbitMQ connection ready ✓")
            break
        except Exception as e:
            if attempt == max_rmq_retries:
                logger.exception("Failed to connect to RabbitMQ after %d attempts.", max_rmq_retries)
                raise
            logger.warning("RabbitMQ connection failed (attempt %d/%d): %s. Retrying in 2s...", attempt, max_rmq_retries, e)
            await asyncio.sleep(2)

    # ── Khai báo queue (idempotent) ──────────
    async with app.state.rmq_connection.channel() as ch:
        # Khai báo queue theo chuẩn API contract: chỉ có durable=True, KHÔNG thêm params khác
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
# Theo API contract mục 3.1
# ─────────────────────────────────────────────
@app.get("/health", tags=["infra"])
async def health():
    """Kiểm tra API còn sống."""
    return {"status": "ok"}


# ─────────────────────────────────────────────
# POST /jobs
# ─────────────────────────────────────────────
class JobCreateRequest(BaseModel):
    payload: str

    @field_validator("payload")
    @classmethod
    def payload_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("payload must not be empty")
        return value


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def create_job(body: JobCreateRequest, request: Request):
    job_id = uuid.uuid4()
    db_pool = request.app.state.db_pool

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                created_at = await conn.fetchval(
                    """
                    INSERT INTO jobs (job_id, payload, status, retry_count)
                    VALUES ($1, $2, 'pending', 0)
                    RETURNING created_at
                    """,
                    job_id,
                    body.payload,
                )
                await conn.execute(
                    """
                    INSERT INTO job_logs (job_id, event, created_at)
                    VALUES ($1, 'created', CURRENT_TIMESTAMP)
                    """,
                    job_id,
                )
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        logger.exception("Could not save new job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )

    message = aio_pika.Message(
        body=json.dumps(
            {"job_id": str(job_id), "payload": body.payload, "retry_count": 0},
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    try:
        async with request.app.state.rmq_connection.channel(
            publisher_confirms=True
        ) as channel:
            await channel.default_exchange.publish(
                message,
                routing_key=MAIN_QUEUE,
                mandatory=True,
            )
    except (
        aio_pika.exceptions.AMQPException,
        aio_pika.exceptions.ChannelInvalidStateError,
        OSError,
        asyncio.TimeoutError,
    ):
        logger.exception("Could not publish job %s to RabbitMQ", job_id)
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'failed',
                            error_message = 'Publish to queue failed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE job_id = $1
                        """,
                        job_id,
                    )
                    await conn.execute(
                        """
                        INSERT INTO job_logs (job_id, event, created_at)
                        VALUES ($1, 'publish_failed', CURRENT_TIMESTAMP)
                        """,
                        job_id,
                    )
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
            logger.exception("Could not record publish failure for job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO job_logs (job_id, event, created_at)
                VALUES ($1, 'published', CURRENT_TIMESTAMP)
                """,
                job_id,
            )
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        logger.exception(
            "Job %s was published, but its published event could not be recorded",
            job_id,
        )

    return {
        "job_id": job_id,
        "status": "pending",
        "created_at": _format_timestamp(created_at),
    }


@app.get("/jobs/{job_id}", tags=["jobs"])
async def get_job(job_id: uuid.UUID, request: Request):
    try:
        async with request.app.state.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT job_id, status, result, error_message, retry_count,
                       created_at, updated_at
                FROM jobs
                WHERE job_id = $1
                """,
                job_id,
            )
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        logger.exception("Could not retrieve job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "result": row["result"],
        "error_message": row["error_message"],
        "retry_count": row["retry_count"],
        "created_at": _format_timestamp(row["created_at"]),
        "updated_at": _format_timestamp(row["updated_at"]),
    }
