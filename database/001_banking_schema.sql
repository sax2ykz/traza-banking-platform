BEGIN;

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_code VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    region VARCHAR(80) NOT NULL,
    onboarding_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_customer_status CHECK (
        onboarding_status IN ('PENDING', 'VERIFIED', 'REJECTED')
    )
);

CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    account_number VARCHAR(30) NOT NULL UNIQUE,
    account_type VARCHAR(20) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'PEN',
    balance NUMERIC(18,2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_account_type CHECK (
        account_type IN ('SAVINGS', 'CHECKING')
    ),
    CONSTRAINT ck_account_currency CHECK (
        currency IN ('PEN', 'USD')
    ),
    CONSTRAINT ck_account_balance CHECK (balance >= 0),
    CONSTRAINT ck_account_status CHECK (
        status IN ('ACTIVE', 'FROZEN', 'CLOSED')
    )
);

CREATE TABLE IF NOT EXISTS cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    card_reference VARCHAR(40) NOT NULL UNIQUE,
    last_four CHAR(4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_card_status CHECK (
        status IN ('ACTIVE', 'BLOCKED', 'EXPIRED')
    ),
    CONSTRAINT ck_card_last_four CHECK (
        last_four ~ '^[0-9]{4}$'
    )
);

CREATE TABLE IF NOT EXISTS loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    principal NUMERIC(18,2) NOT NULL,
    annual_rate NUMERIC(7,4) NOT NULL,
    term_months INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_loan_principal CHECK (principal > 0),
    CONSTRAINT ck_loan_rate CHECK (
        annual_rate >= 0 AND annual_rate <= 100
    ),
    CONSTRAINT ck_loan_term CHECK (term_months > 0),
    CONSTRAINT ck_loan_status CHECK (
        status IN (
            'PENDING', 'APPROVED', 'REJECTED',
            'ACTIVE', 'CLOSED'
        )
    )
);

CREATE TABLE IF NOT EXISTS loan_installments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES loans(id),
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    due_amount NUMERIC(18,2) NOT NULL,
    paid_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',

    CONSTRAINT uq_loan_installment UNIQUE (
        loan_id, installment_number
    ),
    CONSTRAINT ck_installment_number CHECK (
        installment_number > 0
    ),
    CONSTRAINT ck_installment_amount CHECK (
        due_amount > 0
        AND paid_amount >= 0
        AND paid_amount <= due_amount
    ),
    CONSTRAINT ck_installment_status CHECK (
        status IN ('SCHEDULED', 'PARTIAL', 'PAID')
    )
);

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    card_id UUID REFERENCES cards(id),
    loan_id UUID REFERENCES loans(id),
    operation_id UUID NOT NULL DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    transaction_type VARCHAR(30) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    amount NUMERIC(18,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    balance_after NUMERIC(18,2) NOT NULL,
    description VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_transaction_type CHECK (
        transaction_type IN (
            'DEPOSIT', 'WITHDRAWAL', 'CARD_PAYMENT',
            'TRANSFER_IN', 'TRANSFER_OUT',
            'LOAN_DISBURSEMENT', 'REVERSAL'
        )
    ),
    CONSTRAINT ck_transaction_direction CHECK (
        direction IN ('CREDIT', 'DEBIT')
    ),
    CONSTRAINT ck_transaction_amount CHECK (amount > 0),
    CONSTRAINT ck_transaction_currency CHECK (
        currency IN ('PEN', 'USD')
    ),
    CONSTRAINT ck_transaction_balance CHECK (
        balance_after >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_accounts_customer
ON accounts(customer_id);

CREATE INDEX IF NOT EXISTS idx_cards_account
ON cards(account_id);

CREATE INDEX IF NOT EXISTS idx_loans_customer
ON loans(customer_id);

CREATE INDEX IF NOT EXISTS idx_installments_loan
ON loan_installments(loan_id, due_date);

CREATE INDEX IF NOT EXISTS idx_transactions_account_date
ON transactions(account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_operation
ON transactions(operation_id);

COMMIT;
