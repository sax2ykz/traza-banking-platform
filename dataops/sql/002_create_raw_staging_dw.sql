BEGIN;

CREATE SCHEMA IF NOT EXISTS dataops;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS quarantine;
CREATE SCHEMA IF NOT EXISTS dw;

CREATE TABLE IF NOT EXISTS raw.customers (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    customer_code VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    onboarding_status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.accounts (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    customer_id UUID NOT NULL,
    account_number VARCHAR NOT NULL,
    account_type VARCHAR NOT NULL,
    currency CHAR NOT NULL,
    balance NUMERIC NOT NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.transactions (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    account_id UUID NOT NULL,
    card_id UUID,
    loan_id UUID,
    operation_id UUID NOT NULL,
    idempotency_key VARCHAR NOT NULL,
    transaction_type VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    amount NUMERIC NOT NULL,
    currency CHAR NOT NULL,
    balance_after NUMERIC NOT NULL,
    description VARCHAR,
    created_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.banking_operations (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    idempotency_key VARCHAR NOT NULL,
    request_hash CHAR NOT NULL,
    operation_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    source_account_id UUID,
    target_account_id UUID,
    amount NUMERIC NOT NULL,
    currency CHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.loan_applications (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    customer_id UUID NOT NULL,
    requested_amount NUMERIC NOT NULL,
    currency CHAR NOT NULL,
    term_months INTEGER NOT NULL,
    purpose VARCHAR,
    status VARCHAR NOT NULL,
    human_review_required BOOLEAN NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.loans (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    customer_id UUID NOT NULL,
    principal NUMERIC NOT NULL,
    annual_rate NUMERIC NOT NULL,
    term_months INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    loan_application_id UUID,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.loan_installments (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    loan_id UUID NOT NULL,
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    due_amount NUMERIC NOT NULL,
    paid_amount NUMERIC NOT NULL,
    status VARCHAR NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS raw.loan_payments (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    id UUID NOT NULL,
    installment_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    amount NUMERIC NOT NULL,
    status VARCHAR NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, id)
);

CREATE TABLE IF NOT EXISTS staging.customers (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    customer_id UUID NOT NULL,
    customer_code VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    onboarding_status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, customer_id)
);

CREATE TABLE IF NOT EXISTS staging.accounts (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    account_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    account_last4 VARCHAR(8) NOT NULL,
    account_type VARCHAR NOT NULL,
    currency CHAR NOT NULL,
    balance NUMERIC(18,2) NOT NULL,
    status VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, account_id)
);

CREATE TABLE IF NOT EXISTS staging.transactions (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    transaction_id UUID NOT NULL,
    account_id UUID NOT NULL,
    loan_id UUID,
    operation_id UUID NOT NULL,
    transaction_type VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR NOT NULL,
    balance_after NUMERIC(18,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, transaction_id)
);

CREATE TABLE IF NOT EXISTS staging.banking_operations (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    operation_id UUID NOT NULL,
    operation_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    source_account_id UUID,
    target_account_id UUID,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    PRIMARY KEY (run_id, operation_id)
);

CREATE TABLE IF NOT EXISTS staging.loan_applications (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    application_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    requested_amount NUMERIC(18,2) NOT NULL,
    currency CHAR NOT NULL,
    term_months INTEGER NOT NULL,
    purpose VARCHAR,
    status VARCHAR NOT NULL,
    human_review_required BOOLEAN NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ,
    PRIMARY KEY (run_id, application_id)
);

CREATE TABLE IF NOT EXISTS staging.loans (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    loan_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    principal NUMERIC(18,2) NOT NULL,
    annual_rate NUMERIC(10,6) NOT NULL,
    term_months INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    loan_application_id UUID,
    PRIMARY KEY (run_id, loan_id)
);

CREATE TABLE IF NOT EXISTS staging.loan_installments (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    installment_id UUID NOT NULL,
    loan_id UUID NOT NULL,
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    due_amount NUMERIC(18,2) NOT NULL,
    paid_amount NUMERIC(18,2) NOT NULL,
    status VARCHAR NOT NULL,
    PRIMARY KEY (run_id, installment_id)
);

CREATE TABLE IF NOT EXISTS staging.loan_payments (
    run_id UUID NOT NULL REFERENCES dataops.pipeline_runs(run_id),
    payment_id UUID NOT NULL,
    installment_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    status VARCHAR NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, payment_id)
);

CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_customer (
    customer_key BIGSERIAL PRIMARY KEY,
    source_customer_id UUID NOT NULL UNIQUE,
    customer_code VARCHAR NOT NULL,
    region VARCHAR NOT NULL,
    onboarding_status VARCHAR NOT NULL,
    segment VARCHAR NOT NULL DEFAULT 'NO_DEFINIDO',
    created_at TIMESTAMPTZ NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.dim_account (
    account_key BIGSERIAL PRIMARY KEY,
    source_account_id UUID NOT NULL UNIQUE,
    customer_key BIGINT NOT NULL REFERENCES dw.dim_customer(customer_key),
    account_last4 VARCHAR(8) NOT NULL,
    account_type VARCHAR NOT NULL,
    currency CHAR NOT NULL,
    status VARCHAR NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.fact_transactions (
    transaction_key BIGSERIAL PRIMARY KEY,
    source_transaction_id UUID NOT NULL UNIQUE,
    date_key INTEGER NOT NULL REFERENCES dw.dim_date(date_key),
    customer_key BIGINT NOT NULL REFERENCES dw.dim_customer(customer_key),
    account_key BIGINT NOT NULL REFERENCES dw.dim_account(account_key),
    source_loan_id UUID,
    source_operation_id UUID NOT NULL,
    transaction_type VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR NOT NULL,
    balance_after NUMERIC(18,2) NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.fact_loan_applications (
    application_key BIGSERIAL PRIMARY KEY,
    source_application_id UUID NOT NULL UNIQUE,
    date_key INTEGER NOT NULL REFERENCES dw.dim_date(date_key),
    customer_key BIGINT NOT NULL REFERENCES dw.dim_customer(customer_key),
    requested_amount NUMERIC(18,2) NOT NULL,
    currency CHAR NOT NULL,
    term_months INTEGER NOT NULL,
    purpose VARCHAR,
    status VARCHAR NOT NULL,
    human_review_required BOOLEAN NOT NULL,
    reviewed_at TIMESTAMPTZ,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.fact_loans (
    loan_key BIGSERIAL PRIMARY KEY,
    source_loan_id UUID NOT NULL UNIQUE,
    date_key INTEGER NOT NULL REFERENCES dw.dim_date(date_key),
    customer_key BIGINT NOT NULL REFERENCES dw.dim_customer(customer_key),
    source_application_id UUID,
    principal NUMERIC(18,2) NOT NULL,
    annual_rate NUMERIC(10,6) NOT NULL,
    term_months INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.fact_loan_installments (
    installment_key BIGSERIAL PRIMARY KEY,
    source_installment_id UUID NOT NULL UNIQUE,
    loan_key BIGINT NOT NULL REFERENCES dw.fact_loans(loan_key),
    due_date_key INTEGER NOT NULL REFERENCES dw.dim_date(date_key),
    installment_number INTEGER NOT NULL,
    due_amount NUMERIC(18,2) NOT NULL,
    paid_amount NUMERIC(18,2) NOT NULL,
    outstanding_amount NUMERIC(18,2) NOT NULL,
    days_past_due INTEGER NOT NULL DEFAULT 0,
    delinquency_bucket VARCHAR(30) NOT NULL DEFAULT 'AL_DIA',
    status VARCHAR NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS dw.fact_loan_payments (
    payment_key BIGSERIAL PRIMARY KEY,
    source_payment_id UUID NOT NULL UNIQUE,
    payment_date_key INTEGER NOT NULL REFERENCES dw.dim_date(date_key),
    installment_key BIGINT NOT NULL REFERENCES dw.fact_loan_installments(installment_key),
    source_operation_id UUID NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    status VARCHAR NOT NULL,
    last_run_id UUID REFERENCES dataops.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS ix_raw_accounts_run ON raw.accounts(run_id);
CREATE INDEX IF NOT EXISTS ix_raw_transactions_run ON raw.transactions(run_id);
CREATE INDEX IF NOT EXISTS ix_stg_transactions_run ON staging.transactions(run_id);
CREATE INDEX IF NOT EXISTS ix_dw_customer_region ON dw.dim_customer(region);
CREATE INDEX IF NOT EXISTS ix_dw_account_customer ON dw.dim_account(customer_key);
CREATE INDEX IF NOT EXISTS ix_dw_transactions_date ON dw.fact_transactions(date_key);
CREATE INDEX IF NOT EXISTS ix_dw_transactions_customer ON dw.fact_transactions(customer_key);
CREATE INDEX IF NOT EXISTS ix_dw_loan_apps_customer ON dw.fact_loan_applications(customer_key);
CREATE INDEX IF NOT EXISTS ix_dw_installments_bucket ON dw.fact_loan_installments(delinquency_bucket);

COMMIT;
