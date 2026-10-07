BEGIN;

ALTER TABLE raw.accounts
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE raw.transactions
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE raw.banking_operations
    ALTER COLUMN request_hash TYPE VARCHAR(64)
    USING BTRIM(request_hash)::VARCHAR(64);

ALTER TABLE raw.banking_operations
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE raw.loan_applications
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE staging.accounts
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE staging.transactions
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE staging.banking_operations
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE staging.loan_applications
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE dw.dim_account
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE dw.fact_transactions
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

ALTER TABLE dw.fact_loan_applications
    ALTER COLUMN currency TYPE VARCHAR(3)
    USING BTRIM(currency)::VARCHAR(3);

COMMIT;
