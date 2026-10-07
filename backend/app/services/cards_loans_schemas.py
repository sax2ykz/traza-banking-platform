"""Contracts for synthetic cards and consumer-loan requests (development only)."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CardCreate(BaseModel):
    account_id: UUID


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    card_reference: str
    last_four: str
    status: str
    created_at: datetime


class LoanApplicationCreate(BaseModel):
    customer_id: UUID
    requested_amount: Decimal = Field(
        ge=Decimal('500.00'), le=Decimal('50000.00'),
        max_digits=7, decimal_places=2,
        description='Academic simulated limit. Not a real bank credit policy.',
    )
    currency: Literal['PEN', 'USD'] = 'PEN'
    term_months: Literal[6, 12, 18, 24, 36, 48, 60]
    purpose: str = Field(min_length=5, max_length=120)
    disbursement_account_id: UUID


class LoanApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    requested_amount: Decimal
    currency: str
    term_months: int
    purpose: str | None
    disbursement_account_id: UUID | None
    status: str
    human_review_required: bool
    requested_at: datetime
    reviewed_at: datetime | None
