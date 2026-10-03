-- ============================================================
-- Smart Warehouse AI Forecast — Database Initialization
-- SCRUM-13 | Chạy tự động khi container postgres khởi động lần đầu
-- ============================================================

-- Enum-like constraint cho status (kiểm tra ở tầng DB)
-- 5 giá trị theo API contract mục 2
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_status') THEN
        CREATE TYPE job_status AS ENUM (
            'pending',
            'processing',
            'retrying',
            'completed',
            'failed'
        );
    END IF;
END$$;

-- ─────────────────────────────────────────────
-- Bảng jobs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    job_id        UUID PRIMARY KEY,
    payload       TEXT          NOT NULL,
    status        job_status    NOT NULL DEFAULT 'pending',
    result        TEXT,
    error_message TEXT,
    retry_count   INTEGER       NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Index tìm theo status (Worker và Admin hay query)
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);

-- ─────────────────────────────────────────────
-- Bảng job_logs  (1 jobs → nhiều job_logs)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_logs (
    log_id     BIGSERIAL    PRIMARY KEY,
    job_id     UUID         NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    event      VARCHAR(50)  NOT NULL,
    -- Các giá trị event: created | published | processing |
    --                    retry_scheduled | completed | failed | moved_to_dlq
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index để JOIN nhanh jobs → job_logs
CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs (job_id);

-- ─────────────────────────────────────────────
-- Trigger: tự cập nhật updated_at khi UPDATE jobs
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON jobs;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();
