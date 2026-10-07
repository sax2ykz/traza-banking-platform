BEGIN;

CREATE TABLE IF NOT EXISTS dw.fact_banking_operations (
    operation_key BIGSERIAL PRIMARY KEY,

    source_operation_id UUID NOT NULL UNIQUE,

    created_date_key INTEGER NOT NULL
        REFERENCES dw.dim_date(date_key),

    completed_date_key INTEGER
        REFERENCES dw.dim_date(date_key),

    source_account_key BIGINT
        REFERENCES dw.dim_account(account_key),

    target_account_key BIGINT
        REFERENCES dw.dim_account(account_key),

    operation_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,

    amount NUMERIC(18,2) NOT NULL
        CHECK (amount >= 0),

    currency VARCHAR(3) NOT NULL,

    transaction_count INTEGER NOT NULL DEFAULT 0
        CHECK (transaction_count >= 0),

    debit_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (debit_amount >= 0),

    credit_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (credit_amount >= 0),

    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    last_run_id UUID NOT NULL
        REFERENCES dataops.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_created_date
ON dw.fact_banking_operations(created_date_key);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_type
ON dw.fact_banking_operations(operation_type);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_status
ON dw.fact_banking_operations(status);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_source_account
ON dw.fact_banking_operations(source_account_key);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_target_account
ON dw.fact_banking_operations(target_account_key);

CREATE INDEX IF NOT EXISTS
    ix_dw_operations_last_run
ON dw.fact_banking_operations(last_run_id);

COMMIT;
