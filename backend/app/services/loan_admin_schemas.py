from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LoanAdminReview(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    annual_rate: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        le=Decimal("100.0000"),
        max_digits=7,
        decimal_places=4,
        description="TEA de demostración ingresada por el revisor humano. Requerida solo al aprobar.",
    )
    notes: str = Field(default="", max_length=250)


class PendingLoanApplication(BaseModel):
    application_id: UUID
    customer_id: UUID
    customer_code: str
    full_name: str
    requested_amount: Decimal
    currency: str
    term_months: int
    purpose: str | None
    disbursement_account_id: UUID | None
    disbursement_account_last4: str | None = None
    status: str
    human_review_required: bool
    requested_at: datetime


class LoanAdminReviewResult(BaseModel):
    application_id: UUID
    decision: str
    loan_id: UUID | None = None
    installments_created: int = 0
    annual_rate: Decimal | None = None
    disbursement_status: str | None = None
    scheduled_disbursement_at: datetime | None = None
    disbursement_account_last4: str | None = None
