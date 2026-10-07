-- BancoCloud: migracion incremental 002. Ejecutar sobre las seis tablas de 001.
-- No elimina tablas ni datos. En una base con movimientos historicos, revisar
-- primero el agregado de la FK de transactions a banking_operations.
BEGIN;

-- Una solicitud idempotente es la unidad logica de una operacion bancaria.
CREATE TABLE IF NOT EXISTS banking_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    request_hash CHAR(64) NOT NULL,
    operation_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    source_account_id UUID REFERENCES accounts(id),
    target_account_id UUID REFERENCES accounts(id),
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT ck_operation_type CHECK (operation_type IN (
        'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'CARD_PAYMENT',
        'LOAN_DISBURSEMENT', 'LOAN_PAYMENT', 'REVERSAL'
    )),
    CONSTRAINT ck_operation_status CHECK (status IN (
        'PENDING', 'COMPLETED', 'REJECTED', 'REVERSED'
    )),
    CONSTRAINT ck_operation_amount CHECK (amount > 0),
    CONSTRAINT ck_operation_currency CHECK (currency IN ('PEN', 'USD')),
    CONSTRAINT ck_operation_transfer CHECK (
        operation_type <> 'TRANSFER'
        OR (source_account_id IS NOT NULL AND target_account_id IS NOT NULL
            AND source_account_id <> target_account_id)
    )
);

-- Entradas: para operaciones externas se usa una contrapartida sintetica
-- de compensacion (clearing_account_code), no datos bancarios reales.
-- Al completar una operacion, el servicio debera comprobar que
-- SUM(DEBIT) = SUM(CREDIT) por operacion y moneda, en la misma transaccion SQL.
CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id UUID NOT NULL REFERENCES banking_operations(id) ON DELETE RESTRICT,
    sequence_no SMALLINT NOT NULL,
    account_id UUID REFERENCES accounts(id),
    clearing_account_code VARCHAR(40),
    direction VARCHAR(6) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ledger_operation_sequence UNIQUE (operation_id, sequence_no),
    CONSTRAINT ck_ledger_sequence CHECK (sequence_no > 0),
    CONSTRAINT ck_ledger_direction CHECK (direction IN ('DEBIT', 'CREDIT')),
    CONSTRAINT ck_ledger_amount CHECK (amount > 0),
    CONSTRAINT ck_ledger_currency CHECK (currency IN ('PEN', 'USD')),
    CONSTRAINT ck_ledger_counterparty CHECK (
        (account_id IS NOT NULL AND clearing_account_code IS NULL)
        OR (account_id IS NULL AND clearing_account_code IS NOT NULL)
    )
);

-- La solicitud queda separada del prestamo efectivamente concedido.
CREATE TABLE IF NOT EXISTS loan_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    requested_amount NUMERIC(18,2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    term_months INTEGER NOT NULL,
    purpose VARCHAR(120),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    human_review_required BOOLEAN NOT NULL DEFAULT TRUE,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    CONSTRAINT ck_application_amount CHECK (requested_amount > 0),
    CONSTRAINT ck_application_term CHECK (term_months > 0),
    CONSTRAINT ck_application_currency CHECK (currency IN ('PEN', 'USD')),
    CONSTRAINT ck_application_status CHECK (
        status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED')
    )
);

-- Pagos realizados: el total de pagos publicados y loan_installments.paid_amount
-- deben actualizarse atomicamente desde la capa de servicio.
CREATE TABLE IF NOT EXISTS loan_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installment_id UUID NOT NULL REFERENCES loan_installments(id),
    operation_id UUID NOT NULL UNIQUE REFERENCES banking_operations(id),
    amount NUMERIC(18,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'POSTED',
    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_loan_payment_amount CHECK (amount > 0),
    CONSTRAINT ck_loan_payment_status CHECK (status IN ('POSTED', 'REVERSED'))
);

-- Solo metadatos sinteticos y no sensibles, nunca contrasenas ni tokens.
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    result VARCHAR(20) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_audit_actor CHECK (actor_type IN ('CUSTOMER', 'STAFF', 'SERVICE', 'SYSTEM')),
    CONSTRAINT ck_audit_result CHECK (result IN ('SUCCESS', 'DENIED', 'FAILED')),
    CONSTRAINT ck_audit_details_object CHECK (jsonb_typeof(details) = 'object')
);

-- Adaptar la tabla anterior sin borrarla ni recrearla.
ALTER TABLE loans ADD COLUMN IF NOT EXISTS loan_application_id UUID;
CREATE UNIQUE INDEX IF NOT EXISTS uq_loans_loan_application_id
    ON loans (loan_application_id) WHERE loan_application_id IS NOT NULL;

-- Los seis primeros objetos estan vacios al ejecutar esta migracion inicial.
-- Si ya hay transacciones de prueba, detenerse y preparar backfill previo.
DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_loans_loan_application') THEN
        ALTER TABLE loans ADD CONSTRAINT fk_loans_loan_application
            FOREIGN KEY (loan_application_id) REFERENCES loan_applications(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_transactions_operation') THEN
        ALTER TABLE transactions ADD CONSTRAINT fk_transactions_operation
            FOREIGN KEY (operation_id) REFERENCES banking_operations(id);
    END IF;
END;
$migration$;

CREATE INDEX IF NOT EXISTS idx_operations_created ON banking_operations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operations_source ON banking_operations(source_account_id);
CREATE INDEX IF NOT EXISTS idx_ledger_account_date ON ledger_entries(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_operation ON ledger_entries(operation_id);
CREATE INDEX IF NOT EXISTS idx_applications_customer ON loan_applications(customer_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_loan_payments_installment ON loan_payments(installment_id, paid_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(occurred_at DESC);

COMMIT;
