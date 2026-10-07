BEGIN;

CREATE SCHEMA IF NOT EXISTS dataops;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS dw;

CREATE TABLE IF NOT EXISTS dataops.pipeline_runs (
    run_id UUID PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL
        CHECK (status IN (
            'RUNNING',
            'SUCCEEDED',
            'FAILED',
            'QUALITY_GATE_FAILED'
        )),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    source_system VARCHAR(80) NOT NULL DEFAULT 'BancoCloud PostgreSQL',
    rows_extracted INTEGER NOT NULL DEFAULT 0,
    rows_accepted INTEGER NOT NULL DEFAULT 0,
    rows_quarantined INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataops.quality_results (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL
        REFERENCES dataops.pipeline_runs(run_id),
    dataset_name VARCHAR(100) NOT NULL,
    rule_name VARCHAR(120) NOT NULL,
    severity VARCHAR(20) NOT NULL
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    passed BOOLEAN NOT NULL,
    rows_checked INTEGER NOT NULL DEFAULT 0,
    rows_failed INTEGER NOT NULL DEFAULT 0,
    threshold NUMERIC(10,4),
    observed_value NUMERIC(14,4),
    details TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quarantine.rejected_records (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL
        REFERENCES dataops.pipeline_runs(run_id),
    source_table VARCHAR(100) NOT NULL,
    source_record_id VARCHAR(100),
    rule_name VARCHAR(120) NOT NULL,
    reason TEXT NOT NULL,
    payload JSONB NOT NULL,
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_quality_results_run_id
    ON dataops.quality_results(run_id);

CREATE INDEX IF NOT EXISTS ix_quarantine_run_id
    ON quarantine.rejected_records(run_id);

CREATE INDEX IF NOT EXISTS ix_quarantine_source_table
    ON quarantine.rejected_records(source_table);

COMMIT;
