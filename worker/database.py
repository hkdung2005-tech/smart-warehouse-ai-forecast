from contextlib import contextmanager

import psycopg

from worker.config import DATABASE_URL


@contextmanager
def connection():
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


def get_status(job_id: str):
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM jobs WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
        return row[0] if row else None


def update_job(job_id: str, status: str, *, result=None, error=None, retry_count=None, event: str):
    with connection() as conn, conn.cursor() as cur:
        assignments = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
        values = [status]
        if result is not None:
            assignments.append("result = %s")
            values.append(result)
        if error is not None or status in ("completed", "processing", "retrying"):
            assignments.append("error_message = %s")
            values.append(error)
        if retry_count is not None:
            assignments.append("retry_count = %s")
            values.append(retry_count)
        values.append(job_id)
        cur.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id = %s", values)
        if cur.rowcount == 0:
            raise LookupError(f"job {job_id} does not exist")
        cur.execute("INSERT INTO job_logs (job_id, event, created_at) VALUES (%s, %s, CURRENT_TIMESTAMP)", (job_id, event))

