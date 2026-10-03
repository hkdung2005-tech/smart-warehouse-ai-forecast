import json
import logging
import signal
import threading
import time

import pika

from worker import database
from worker.config import MAX_RETRIES, MAIN_QUEUE, PREFETCH_COUNT, RABBITMQ_URL, RATE_LIMIT_PER_SECOND, RETRY_DELAYS_SECONDS, DLQ
from worker.gemini_client import GeminiError, generate
from worker.queues import declare_topology

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")
_stop = threading.Event()
_last_call = 0.0
_rate_lock = threading.Lock()


def _rate_limit():
    global _last_call
    with _rate_lock:
        interval = 1 / RATE_LIMIT_PER_SECOND
        wait = interval - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _publish(channel, queue: str, body: bytes, headers: dict):
    channel.basic_publish(
        exchange="", routing_key=queue, body=body,
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json", headers=headers),
        mandatory=True,
    )


def _handle(channel, method, properties, body):
    try:
        job = json.loads(body)
        job_id, payload = job.get("job_id"), job.get("payload")
        retries = int(job.get("retry_count", 0))
        if not isinstance(job_id, str) or not job_id or not isinstance(payload, str) or not payload.strip():
            raise ValueError("message must contain non-empty job_id and payload")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        log.error("Discarding malformed message: %s", exc)
        try:
            _publish(channel, DLQ, body, {"x-error": str(exc)[:500]})
            channel.basic_ack(method.delivery_tag)
        except Exception:
            log.exception("Could not move malformed message to DLQ")
            channel.basic_nack(method.delivery_tag, requeue=True)
        return

    try:
        current_status = database.get_status(job_id)
        if current_status is None:
            log.error("Job %s is missing from PostgreSQL; retaining message for recovery", job_id)
            channel.basic_nack(method.delivery_tag, requeue=True)
            time.sleep(1)
            return
        if current_status in ("completed", "failed"):
            channel.basic_ack(method.delivery_tag)
            return
        database.update_job(job_id, "processing", retry_count=retries, event="processing")
        _rate_limit()
        result = generate(payload)
        database.update_job(job_id, "completed", result=result, retry_count=retries, event="completed")
        channel.basic_ack(method.delivery_tag)
    except GeminiError as exc:
        status_code = exc.status_code
        retryable = status_code is None or status_code == 429 or status_code >= 500
        if retryable and retries < MAX_RETRIES:
            next_retry = retries + 1
            delay = RETRY_DELAYS_SECONDS[min(next_retry - 1, len(RETRY_DELAYS_SECONDS) - 1)]
            retry_queue = f"{MAIN_QUEUE}.retry.{delay}s"
            updated = dict(job, retry_count=next_retry)
            try:
                # Record DB state before publishing; if publish fails, requeue original.
                database.update_job(job_id, "retrying", error=str(exc), retry_count=next_retry, event="retry_scheduled")
                _publish(channel, retry_queue, json.dumps(updated).encode(), {"x-retry-count": next_retry})
                channel.basic_ack(method.delivery_tag)
            except Exception:
                log.exception("Could not schedule retry for %s", job_id)
                channel.basic_nack(method.delivery_tag, requeue=True)
        else:
            try:
                reason = str(exc)
                if retryable:
                    # Publish the durable DLQ copy before recording a terminal state;
                    # otherwise a publish failure could leave a failed job without a DLQ message.
                    _publish(channel, DLQ, body, {"x-error": reason[:500], "x-retry-count": retries})
                    event = "moved_to_dlq"
                else:
                    event = "failed"
                database.update_job(job_id, "failed", error=reason, retry_count=retries, event=event)
                channel.basic_ack(method.delivery_tag)
            except Exception:
                log.exception("Could not persist terminal failure for %s", job_id)
                channel.basic_nack(method.delivery_tag, requeue=True)
    except Exception:
        # Includes DB/network failures: never ack until the durable state transition succeeds.
        log.exception("Unexpected processing failure for %s", job_id)
        channel.basic_nack(method.delivery_tag, requeue=True)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    params.heartbeat = 60
    params.blocked_connection_timeout = 30
    while not _stop.is_set():
        connection = None
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            declare_topology(channel)
            channel.confirm_delivery()
            channel.basic_qos(prefetch_count=PREFETCH_COUNT)
            channel.basic_consume(queue=MAIN_QUEUE, on_message_callback=_handle, auto_ack=False)
            log.info("Consuming %s (prefetch=%s, rate limit=%s/s)", MAIN_QUEUE, PREFETCH_COUNT, RATE_LIMIT_PER_SECOND)
            channel.start_consuming()
        except Exception:
            if not _stop.is_set():
                log.exception("RabbitMQ consumer disconnected; reconnecting in 3 seconds")
                time.sleep(3)
        finally:
            if connection and connection.is_open:
                connection.close()


def _shutdown(*_):
    _stop.set()


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)
main()
