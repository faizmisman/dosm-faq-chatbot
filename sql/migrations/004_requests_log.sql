-- Create requests_log table to capture API requests with minimal fields
-- Safe to run once; idempotency can be enforced via IF NOT EXISTS

CREATE TABLE IF NOT EXISTS requests_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_ip TEXT,
    route TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INT NOT NULL,
    latency_ms INT,
    model_version TEXT,
    query TEXT,
    response_summary TEXT
);

-- Helpful index for time-range queries
CREATE INDEX IF NOT EXISTS idx_requests_log_created_at ON requests_log (created_at);
CREATE INDEX IF NOT EXISTS idx_requests_log_route ON requests_log (route);
