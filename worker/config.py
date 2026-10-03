import os


def _integer(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/warehouse")
GEMINI_API_URL = os.getenv("GEMINI_API_URL", "http://localhost:9000/generate")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MAIN_QUEUE = os.getenv("MAIN_QUEUE", "jobs")
DLQ = os.getenv("DLQ", "jobs.dlq")
MAX_RETRIES = _integer("MAX_RETRIES", 3, 0)
RATE_LIMIT_PER_SECOND = _integer("RATE_LIMIT_PER_SECOND", 10)
PREFETCH_COUNT = _integer("PREFETCH_COUNT", 1)
RETRY_DELAYS_SECONDS = (1, 2, 4)
