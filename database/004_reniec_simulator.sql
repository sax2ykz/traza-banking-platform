-- BancoCloud - Synthetic RENIEC Simulator
-- Academic/local PoC only. Contains fictitious identity data.
-- It is NOT connected to RENIEC or any real identity provider.

CREATE TABLE IF NOT EXISTS reniec_simulated_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_number VARCHAR(8) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    birth_date DATE NOT NULL,
    document_status VARCHAR(20) NOT NULL,
    ubigeo VARCHAR(6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_reniec_document_number
        CHECK (document_number ~ '^[0-9]{8}$'),

    CONSTRAINT ck_reniec_document_status
        CHECK (document_status IN ('CURRENT', 'NOT_CURRENT')),

    CONSTRAINT ck_reniec_ubigeo
        CHECK (ubigeo ~ '^[0-9]{6}$')
);


CREATE TABLE IF NOT EXISTS identity_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    customer_id UUID NOT NULL
        REFERENCES customers(id),

    document_number VARCHAR(8) NOT NULL,

    claimed_full_name VARCHAR(150) NOT NULL,
    claimed_birth_date DATE NOT NULL,

    result VARCHAR(20) NOT NULL,

    evidence_ref VARCHAR(80) NOT NULL UNIQUE,

    registry_document_status VARCHAR(20),

    matched_name BOOLEAN NOT NULL DEFAULT FALSE,
    matched_birth_date BOOLEAN NOT NULL DEFAULT FALSE,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_identity_document_number
        CHECK (document_number ~ '^[0-9]{8}$'),

    CONSTRAINT ck_identity_verification_result
        CHECK (
            result IN (
                'MATCH',
                'MISMATCH',
                'NOT_FOUND',
                'NOT_CURRENT'
            )
        ),

    CONSTRAINT ck_identity_evidence_ref
        CHECK (
            evidence_ref ~ '^SIM-RENIEC-[A-Za-z0-9_-]{8,60}$'
        )
);


CREATE INDEX IF NOT EXISTS ix_identity_verifications_customer
    ON identity_verifications(customer_id, verified_at DESC);


CREATE INDEX IF NOT EXISTS ix_identity_verifications_document
    ON identity_verifications(document_number);


-- ------------------------------------------------------------------
-- Synthetic test identities
-- Fictitious data created exclusively for BancoCloud demonstrations.
-- ------------------------------------------------------------------

INSERT INTO reniec_simulated_registry (
    document_number,
    full_name,
    birth_date,
    document_status,
    ubigeo
)
VALUES
    (
        '70000001',
        'Cliente Demo BancoCloud',
        DATE '2001-05-14',
        'CURRENT',
        '150101'
    ),
    (
        '70000002',
        'Ana Torres Demo',
        DATE '1998-11-08',
        'CURRENT',
        '150122'
    ),
    (
        '70000003',
        'Carlos Mendoza Demo',
        DATE '1995-03-21',
        'NOT_CURRENT',
        '040101'
    ),
    (
        '70000004',
        'Lucia Fernandez Demo',
        DATE '2000-07-17',
        'CURRENT',
        '130101'
    )
ON CONFLICT (document_number) DO NOTHING;