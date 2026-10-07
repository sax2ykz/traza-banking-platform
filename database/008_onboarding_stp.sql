-- BancoCloud migration 008: STP onboarding + exception queue.
-- Extends the existing P0 onboarding without replacing human review.
-- No LLM may decide VERIFIED.

BEGIN;

-- ------------------------------------------------------------------
-- 1. Allow REVIEW_REQUIRED as an explicit onboarding state.
-- ------------------------------------------------------------------

ALTER TABLE customers
    DROP CONSTRAINT IF EXISTS ck_customer_status;

ALTER TABLE customers
    ADD CONSTRAINT ck_customer_status
    CHECK (
        onboarding_status IN (
            'PENDING',
            'REVIEW_REQUIRED',
            'VERIFIED',
            'REJECTED'
        )
    );

-- ------------------------------------------------------------------
-- 2. Operational queue for STP exceptions.
--    onboarding_reviews remains the source of HUMAN final decisions.
-- ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS onboarding_exception_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    customer_id UUID NOT NULL
        REFERENCES customers(id),

    identity_verification_id UUID NOT NULL
        REFERENCES identity_verifications(id),

    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',

    reason VARCHAR(40) NOT NULL,

    priority VARCHAR(15) NOT NULL DEFAULT 'MEDIUM',

    severity VARCHAR(15) NOT NULL DEFAULT 'MEDIUM',

    rule_version VARCHAR(30) NOT NULL,

    assigned_to UUID
        REFERENCES app_users(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    assigned_at TIMESTAMPTZ,

    sla_due_at TIMESTAMPTZ NOT NULL,

    resolved_at TIMESTAMPTZ,

    CONSTRAINT uq_onboarding_exception_verification
        UNIQUE (identity_verification_id),

    CONSTRAINT ck_onboarding_exception_status
        CHECK (
            status IN (
                'OPEN',
                'ASSIGNED',
                'RESOLVED'
            )
        ),

    CONSTRAINT ck_onboarding_exception_reason
        CHECK (
            reason IN (
                'IDENTITY_MISMATCH',
                'DOCUMENT_NOT_CURRENT',
                'IDENTITY_NOT_FOUND',
                'INSUFFICIENT_EVIDENCE',
                'BUSINESS_RULE_ALERT',
                'TECHNICAL_ERROR'
            )
        ),

    CONSTRAINT ck_onboarding_exception_priority
        CHECK (
            priority IN (
                'LOW',
                'MEDIUM',
                'HIGH'
            )
        ),

    CONSTRAINT ck_onboarding_exception_severity
        CHECK (
            severity IN (
                'LOW',
                'MEDIUM',
                'HIGH'
            )
        ),

    CONSTRAINT ck_onboarding_exception_assignment
        CHECK (
            (
                status = 'OPEN'
                AND assigned_to IS NULL
                AND assigned_at IS NULL
            )
            OR
            (
                status = 'ASSIGNED'
                AND assigned_to IS NOT NULL
                AND assigned_at IS NOT NULL
                AND resolved_at IS NULL
            )
            OR
            (
                status = 'RESOLVED'
                AND resolved_at IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS
    ix_onboarding_exception_status_created
    ON onboarding_exception_cases (
        status,
        created_at
    );

CREATE INDEX IF NOT EXISTS
    ix_onboarding_exception_assigned
    ON onboarding_exception_cases (
        assigned_to,
        status
    );

CREATE INDEX IF NOT EXISTS
    ix_onboarding_exception_customer
    ON onboarding_exception_cases (
        customer_id,
        created_at DESC
    );

-- Prevent more than one active exception for the same customer.
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_onboarding_exception_active_customer
    ON onboarding_exception_cases (customer_id)
    WHERE status IN ('OPEN', 'ASSIGNED');

COMMIT;
