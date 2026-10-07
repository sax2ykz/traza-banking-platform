-- BancoCloud migration 006: scheduled, idempotent loan disbursement.
-- Incremental only: no tables or existing business records are deleted.
BEGIN;

ALTER TABLE public.loan_applications
    ADD COLUMN IF NOT EXISTS disbursement_account_id UUID;

ALTER TABLE public.loans
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approved_by_user_id UUID,
    ADD COLUMN IF NOT EXISTS disbursement_account_id UUID,
    ADD COLUMN IF NOT EXISTS disbursement_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS scheduled_disbursement_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS disbursed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS disbursement_operation_id UUID;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_loan_application_disbursement_account'
    ) THEN
        ALTER TABLE public.loan_applications
            ADD CONSTRAINT fk_loan_application_disbursement_account
            FOREIGN KEY (disbursement_account_id)
            REFERENCES public.accounts(id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_loan_disbursement_account'
    ) THEN
        ALTER TABLE public.loans
            ADD CONSTRAINT fk_loan_disbursement_account
            FOREIGN KEY (disbursement_account_id)
            REFERENCES public.accounts(id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_loan_approved_by_user'
    ) THEN
        ALTER TABLE public.loans
            ADD CONSTRAINT fk_loan_approved_by_user
            FOREIGN KEY (approved_by_user_id)
            REFERENCES public.app_users(id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_loan_disbursement_operation'
    ) THEN
        ALTER TABLE public.loans
            ADD CONSTRAINT fk_loan_disbursement_operation
            FOREIGN KEY (disbursement_operation_id)
            REFERENCES public.banking_operations(id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_loan_disbursement_status'
    ) THEN
        ALTER TABLE public.loans
            ADD CONSTRAINT ck_loan_disbursement_status
            CHECK (
                disbursement_status IN (
                    'PENDING',
                    'SCHEDULED',
                    'PROCESSING',
                    'COMPLETED',
                    'FAILED'
                )
            );
    END IF;
END;
$migration$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_loans_disbursement_operation_id
    ON public.loans(disbursement_operation_id)
    WHERE disbursement_operation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_loans_disbursement_due
    ON public.loans(disbursement_status, scheduled_disbursement_at)
    WHERE disbursement_status = 'SCHEDULED';

CREATE INDEX IF NOT EXISTS idx_loan_applications_disbursement_account
    ON public.loan_applications(disbursement_account_id);

COMMIT;
