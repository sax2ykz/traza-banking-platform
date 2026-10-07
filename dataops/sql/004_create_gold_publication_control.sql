BEGIN;

CREATE TABLE IF NOT EXISTS dataops.published_batches (
    batch_id UUID PRIMARY KEY,
    source_run_id UUID NOT NULL UNIQUE
        REFERENCES dataops.pipeline_runs(run_id),

    publication_status VARCHAR(30) NOT NULL
        CHECK (publication_status IN ('PUBLISHED', 'REJECTED')),

    is_current BOOLEAN NOT NULL DEFAULT FALSE,

    gold_row_count INTEGER NOT NULL DEFAULT 0
        CHECK (gold_row_count >= 0),

    quality_gate_total INTEGER NOT NULL DEFAULT 0
        CHECK (quality_gate_total >= 0),

    quality_gate_passed INTEGER NOT NULL DEFAULT 0
        CHECK (
            quality_gate_passed >= 0
            AND quality_gate_passed <= quality_gate_total
        ),

    rows_quarantined INTEGER NOT NULL DEFAULT 0
        CHECK (rows_quarantined >= 0),

    published_at TIMESTAMPTZ,
    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS
    ux_published_batches_one_current
ON dataops.published_batches ((is_current))
WHERE is_current = TRUE;

CREATE OR REPLACE VIEW dataops.current_published_batch AS
SELECT
    batch_id,
    source_run_id,
    publication_status,
    gold_row_count,
    quality_gate_total,
    quality_gate_passed,
    rows_quarantined,
    published_at,
    notes,
    created_at
FROM dataops.published_batches
WHERE is_current = TRUE;

COMMIT;
