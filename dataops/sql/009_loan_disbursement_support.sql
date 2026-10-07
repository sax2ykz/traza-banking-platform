-- BancoCloud DataOps migration 009: preserve loan lineage for disbursements.
BEGIN;

ALTER TABLE staging.transactions
    ADD COLUMN IF NOT EXISTS loan_id UUID;

ALTER TABLE dw.fact_transactions
    ADD COLUMN IF NOT EXISTS source_loan_id UUID;

CREATE INDEX IF NOT EXISTS ix_staging_transactions_loan
    ON staging.transactions(run_id, loan_id);

CREATE INDEX IF NOT EXISTS ix_dw_transactions_loan
    ON dw.fact_transactions(source_loan_id)
    WHERE source_loan_id IS NOT NULL;

COMMIT;

-- IMPORTANT:
-- After this migration, re-run 006_create_gold_publish_function.sql so the
-- CREATE OR REPLACE FUNCTION dataops.publish_gold(UUID) includes support for
-- source_loan_id and LOAN_DISBURSEMENT reconciliation.
