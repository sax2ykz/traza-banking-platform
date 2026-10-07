BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;


-- ============================================================
-- 1. METADATA / REPRODUCIBILIDAD DEL DATASET
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dataset_runs (
    dataset_version VARCHAR(50) PRIMARY KEY,

    seed INTEGER NOT NULL,

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    requested_customers INTEGER NOT NULL
        CHECK (requested_customers > 0),

    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    notes TEXT,

    CHECK (period_end >= period_start)
);


-- ============================================================
-- 2. DIMENSION FECHA
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,

    full_date DATE NOT NULL UNIQUE,

    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL
        CHECK (quarter BETWEEN 1 AND 4),

    month INTEGER NOT NULL
        CHECK (month BETWEEN 1 AND 12),

    month_name VARCHAR(20) NOT NULL,

    day INTEGER NOT NULL
        CHECK (day BETWEEN 1 AND 31),

    weekday INTEGER NOT NULL
        CHECK (weekday BETWEEN 1 AND 7),

    is_weekend BOOLEAN NOT NULL
);


-- ============================================================
-- 3. CLIENTES SINTETICOS
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.synthetic_customers (
    customer_id UUID PRIMARY KEY,

    customer_code VARCHAR(30) NOT NULL UNIQUE,

    onboarding_date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    region VARCHAR(20) NOT NULL
        CHECK (
            region IN (
                'LIMA',
                'NORTE',
                'CENTRO',
                'SUR'
            )
        ),

    segment VARCHAR(20) NOT NULL
        CHECK (
            segment IN (
                'MASIVO',
                'PREFERENTE',
                'PYME'
            )
        ),

    active BOOLEAN NOT NULL DEFAULT TRUE,

    dataset_version VARCHAR(50) NOT NULL
        REFERENCES analytics.dataset_runs(dataset_version)
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_customers_region
ON analytics.synthetic_customers(region);

CREATE INDEX IF NOT EXISTS
    ix_analytics_customers_segment
ON analytics.synthetic_customers(segment);

CREATE INDEX IF NOT EXISTS
    ix_analytics_customers_dataset
ON analytics.synthetic_customers(dataset_version);


-- ============================================================
-- 4. TRANSACCIONES SINTETICAS
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.synthetic_transactions (
    transaction_id UUID PRIMARY KEY,

    customer_id UUID NOT NULL
        REFERENCES analytics.synthetic_customers(customer_id),

    date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    operation_type VARCHAR(20) NOT NULL
        CHECK (
            operation_type IN (
                'DEPOSIT',
                'WITHDRAWAL',
                'TRANSFER'
            )
        ),

    channel VARCHAR(20) NOT NULL
        CHECK (
            channel IN (
                'MOBILE',
                'WEB',
                'ATM',
                'BRANCH'
            )
        ),

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'COMPLETED',
                'REJECTED'
            )
        ),

    amount NUMERIC(18,2) NOT NULL
        CHECK (amount > 0),

    fee_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (fee_amount >= 0),

    currency VARCHAR(3) NOT NULL DEFAULT 'PEN'
        CHECK (currency = 'PEN'),

    dataset_version VARCHAR(50) NOT NULL
        REFERENCES analytics.dataset_runs(dataset_version)
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_transactions_date
ON analytics.synthetic_transactions(date_key);

CREATE INDEX IF NOT EXISTS
    ix_analytics_transactions_customer
ON analytics.synthetic_transactions(customer_id);

CREATE INDEX IF NOT EXISTS
    ix_analytics_transactions_type
ON analytics.synthetic_transactions(operation_type);

CREATE INDEX IF NOT EXISTS
    ix_analytics_transactions_dataset
ON analytics.synthetic_transactions(dataset_version);


-- ============================================================
-- 5. PRESTAMOS SINTETICOS
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.synthetic_loans (
    loan_id UUID PRIMARY KEY,

    customer_id UUID NOT NULL
        REFERENCES analytics.synthetic_customers(customer_id),

    origination_date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    principal NUMERIC(18,2) NOT NULL
        CHECK (principal > 0),

    annual_rate NUMERIC(7,4) NOT NULL
        CHECK (
            annual_rate > 0
            AND annual_rate <= 100
        ),

    term_months INTEGER NOT NULL
        CHECK (
            term_months IN (
                6, 12, 18, 24, 36
            )
        ),

    current_balance NUMERIC(18,2) NOT NULL
        CHECK (current_balance >= 0),

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'ACTIVE',
                'CLOSED',
                'DELINQUENT'
            )
        ),

    dataset_version VARCHAR(50) NOT NULL
        REFERENCES analytics.dataset_runs(dataset_version)
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_loans_customer
ON analytics.synthetic_loans(customer_id);

CREATE INDEX IF NOT EXISTS
    ix_analytics_loans_status
ON analytics.synthetic_loans(status);

CREATE INDEX IF NOT EXISTS
    ix_analytics_loans_dataset
ON analytics.synthetic_loans(dataset_version);


-- ============================================================
-- 6. CUOTAS / MOROSIDAD
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.synthetic_loan_installments (
    installment_id UUID PRIMARY KEY,

    loan_id UUID NOT NULL
        REFERENCES analytics.synthetic_loans(loan_id),

    installment_number INTEGER NOT NULL
        CHECK (installment_number > 0),

    due_date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    paid_date_key INTEGER
        REFERENCES analytics.dim_date(date_key),

    due_amount NUMERIC(18,2) NOT NULL
        CHECK (due_amount > 0),

    paid_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (paid_amount >= 0),

    outstanding_amount NUMERIC(18,2) NOT NULL
        CHECK (outstanding_amount >= 0),

    days_past_due INTEGER NOT NULL DEFAULT 0
        CHECK (days_past_due >= 0),

    delinquency_bucket VARCHAR(20) NOT NULL
        CHECK (
            delinquency_bucket IN (
                'AL_DIA',
                '1_30',
                '31_60',
                '61_90',
                '90_PLUS'
            )
        ),

    status VARCHAR(20) NOT NULL
        CHECK (
            status IN (
                'PAID',
                'PARTIAL',
                'PENDING',
                'OVERDUE'
            )
        ),

    dataset_version VARCHAR(50) NOT NULL
        REFERENCES analytics.dataset_runs(dataset_version),

    UNIQUE (loan_id, installment_number),

    CHECK (paid_amount <= due_amount)
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_installments_bucket
ON analytics.synthetic_loan_installments(delinquency_bucket);

CREATE INDEX IF NOT EXISTS
    ix_analytics_installments_due_date
ON analytics.synthetic_loan_installments(due_date_key);

CREATE INDEX IF NOT EXISTS
    ix_analytics_installments_dataset
ON analytics.synthetic_loan_installments(dataset_version);


-- ============================================================
-- 7. RENTABILIDAD MENSUAL POR PRODUCTO Y SEGMENTO
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.synthetic_profitability_monthly (
    metric_id BIGSERIAL PRIMARY KEY,

    period_month_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    segment VARCHAR(20) NOT NULL
        CHECK (
            segment IN (
                'MASIVO',
                'PREFERENTE',
                'PYME'
            )
        ),

    product VARCHAR(30) NOT NULL
        CHECK (
            product IN (
                'SAVINGS',
                'CHECKING',
                'CONSUMER_LOAN'
            )
        ),

    active_customers INTEGER NOT NULL DEFAULT 0
        CHECK (active_customers >= 0),

    transaction_count INTEGER NOT NULL DEFAULT 0
        CHECK (transaction_count >= 0),

    transaction_amount NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (transaction_amount >= 0),

    outstanding_balance NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (outstanding_balance >= 0),

    interest_income NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (interest_income >= 0),

    fee_income NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (fee_income >= 0),

    funding_cost NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (funding_cost >= 0),

    allocated_operating_cost NUMERIC(18,2) NOT NULL DEFAULT 0
        CHECK (allocated_operating_cost >= 0),

    estimated_operating_margin NUMERIC(18,2)
        GENERATED ALWAYS AS (
            interest_income
            + fee_income
            - funding_cost
            - allocated_operating_cost
        ) STORED,

    dataset_version VARCHAR(50) NOT NULL
        REFERENCES analytics.dataset_runs(dataset_version),

    UNIQUE (
        dataset_version,
        period_month_key,
        segment,
        product
    )
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_profitability_period
ON analytics.synthetic_profitability_monthly(period_month_key);

CREATE INDEX IF NOT EXISTS
    ix_analytics_profitability_segment
ON analytics.synthetic_profitability_monthly(segment);

CREATE INDEX IF NOT EXISTS
    ix_analytics_profitability_product
ON analytics.synthetic_profitability_monthly(product);


COMMIT;
