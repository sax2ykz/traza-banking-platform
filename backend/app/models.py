"""BancoCloud: mappings for migrations 001 and 002 (not schema-creation code)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def pk_uuid() -> Mapped[UUID]:
    return mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[UUID] = pk_uuid()
    customer_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(80), nullable=False)
    onboarding_status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[UUID] = pk_uuid()
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    account_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'PEN'"), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), server_default=text("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'ACTIVE'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[UUID] = pk_uuid()
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    card_reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'ACTIVE'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    id: Mapped[UUID] = pk_uuid()
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'PEN'"), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str | None] = mapped_column(String(120))
    disbursement_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"), nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[UUID] = pk_uuid()
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    principal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    loan_application_id: Mapped[UUID | None] = mapped_column(ForeignKey("loan_applications.id"), unique=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The SQL migration enforces the FK to app_users; app_users uses SecurityBase.
    approved_by_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    disbursement_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    disbursement_status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"), nullable=False)
    scheduled_disbursement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disbursement_operation_id: Mapped[UUID | None] = mapped_column(ForeignKey("banking_operations.id"), unique=True)


class LoanInstallment(Base):
    __tablename__ = "loan_installments"
    id: Mapped[UUID] = pk_uuid()
    loan_id: Mapped[UUID] = mapped_column(ForeignKey("loans.id"), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), server_default=text("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'SCHEDULED'"), nullable=False)


class BankingOperation(Base):
    __tablename__ = "banking_operations"
    id: Mapped[UUID] = pk_uuid()
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"), nullable=False)
    source_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    target_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[UUID] = pk_uuid()
    operation_id: Mapped[UUID] = mapped_column(ForeignKey("banking_operations.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    clearing_account_code: Mapped[str | None] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[UUID] = pk_uuid()
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    card_id: Mapped[UUID | None] = mapped_column(ForeignKey("cards.id"))
    loan_id: Mapped[UUID | None] = mapped_column(ForeignKey("loans.id"))
    operation_id: Mapped[UUID] = mapped_column(ForeignKey("banking_operations.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class LoanPayment(Base):
    __tablename__ = "loan_payments"
    id: Mapped[UUID] = pk_uuid()
    installment_id: Mapped[UUID] = mapped_column(ForeignKey("loan_installments.id"), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(ForeignKey("banking_operations.id"), unique=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'POSTED'"), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = pk_uuid()
    correlation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
