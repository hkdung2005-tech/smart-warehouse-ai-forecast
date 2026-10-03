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
# Các route nghiệp vụ — Chấn implement (SCRUM-12)
# ─────────────────────────────────────────────
# POST /jobs           → tạo job, lưu DB, đẩy RabbitMQ
# GET  /jobs/{job_id}  → tra cứu trạng thái job