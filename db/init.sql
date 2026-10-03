-- ============================================================
-- Smart Warehouse AI Forecast — Database Initialization
-- SCRUM-13 | Chạy tự động khi container postgres khởi động lần đầu
-- ============================================================

-- status dùng VARCHAR(20) + CHECK constraint thay vì custom ENUM
-- để Worker (psycopg) có thể UPDATE trực tiếp bằng string không cần cast
-- 5 giá trị theo API contract mục 2

-- ─────────────────────────────────────────────
-- Bảng jobs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    job_id        UUID         PRIMARY KEY,
    payload       TEXT         NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending','processing','retrying','completed','failed')),
    result        TEXT,
    error_message TEXT,
    retry_count   INTEGER      NOT NULL DEFAULT 0,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Bảng job_logs  (1 jobs → nhiều job_logs)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_logs (
    log_id     BIGSERIAL    PRIMARY KEY,
    job_id     UUID         NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    event      VARCHAR(50)  NOT NULL,
    -- API ghi:    created | published | publish_failed
    -- Worker ghi: processing | completed | retry_scheduled | moved_to_dlq | failed
    created_at TIMESTAMP  NOT NULL DEFAULT NOW()
);
