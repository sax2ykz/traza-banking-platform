-- BANCOCLOUD migration 003: LOCAL synthetic users and review records.
-- Never use real personal data or real identity documentation.
BEGIN;
CREATE TABLE IF NOT EXISTS app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    customer_id UUID UNIQUE REFERENCES customers(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_auth_role CHECK (role IN ('ADMIN','CUSTOMER')),
    CONSTRAINT ck_auth_binding CHECK ((role='ADMIN' AND customer_id IS NULL) OR (role='CUSTOMER' AND customer_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS onboarding_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    reviewer_id UUID NOT NULL REFERENCES app_users(id),
    decision VARCHAR(15) NOT NULL,
    evidence_ref VARCHAR(80) NOT NULL,
    document_checked BOOLEAN NOT NULL,
    data_consistent BOOLEAN NOT NULL,
    notes VARCHAR(250) NOT NULL DEFAULT '',
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_onboarding_decision CHECK (decision IN ('VERIFIED', 'REJECTED')),
    CONSTRAINT ck_onboarding_checks CHECK (decision <> 'VERIFIED' OR (document_checked AND data_consistent))
);
CREATE INDEX IF NOT EXISTS idx_users_customer ON app_users(customer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_customer ON onboarding_reviews(customer_id, reviewed_at DESC);
COMMIT;
