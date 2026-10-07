from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CustomerLoanSummary(BaseModel):
    id: UUID
    customer_id: UUID
    loan_application_id: UUID | None
    principal: Decimal
    currency: str
    annual_rate: Decimal
    term_months: int
    status: str
    requested_at: datetime
    approved_at: datetime | None
    disbursement_status: str
    scheduled_disbursement_at: datetime | None
    disbursed_at: datetime | None
    disbursement_operation_id: UUID | None
    disbursement_account_id: UUID | None
    disbursement_account_last4: str | None
    installment_count: int
    installment_amount: Decimal | None
    total_scheduled: Decimal
    total_paid: Decimal
    outstanding_amount: Decimal
    next_due_date: date | None
    next_due_amount: Decimal | None


class LoanInstallmentDetail(BaseModel):
    id: UUID
    loan_id: UUID
    installment_number: int
    due_date: date
    due_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    status: str
