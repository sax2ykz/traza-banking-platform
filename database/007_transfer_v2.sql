-- BancoCloud / TRAZA - Transferencias V2
-- Migración incremental: agrega soporte para transferencia interbancaria académica.
-- No elimina operaciones ni modifica saldos.
BEGIN;

ALTER TABLE public.banking_operations
    DROP CONSTRAINT IF EXISTS ck_operation_type;

ALTER TABLE public.banking_operations
    ADD CONSTRAINT ck_operation_type CHECK (
        operation_type IN (
            'DEPOSIT',
            'WITHDRAWAL',
            'TRANSFER',
            'INTERBANK_TRANSFER',
            'CARD_PAYMENT',
            'LOAN_DISBURSEMENT',
            'LOAN_PAYMENT',
            'REVERSAL'
        )
    );

ALTER TABLE public.banking_operations
    DROP CONSTRAINT IF EXISTS ck_operation_transfer;

ALTER TABLE public.banking_operations
    ADD CONSTRAINT ck_operation_transfer CHECK (
        operation_type <> 'TRANSFER'
        OR (
            source_account_id IS NOT NULL
            AND target_account_id IS NOT NULL
            AND source_account_id <> target_account_id
        )
    );

ALTER TABLE public.banking_operations
    DROP CONSTRAINT IF EXISTS ck_operation_interbank_transfer;

ALTER TABLE public.banking_operations
    ADD CONSTRAINT ck_operation_interbank_transfer CHECK (
        operation_type <> 'INTERBANK_TRANSFER'
        OR (
            source_account_id IS NOT NULL
            AND target_account_id IS NULL
        )
    );

COMMIT;
