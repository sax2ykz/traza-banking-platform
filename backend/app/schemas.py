"""Input and output contracts for local-only development endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    customer_code: str = Field(min_length=5, max_length=30, pattern=r"^BC-[A-Z0-9-]+$")
    full_name: str = Field(min_length=3, max_length=150)
    email: str = Field(min_length=5, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    region: str = Field(min_length=2, max_length=80)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_code: str
    full_name: str
    email: str
    region: str
    onboarding_status: str
    created_at: datetime


class AccountCreate(BaseModel):
    customer_id: UUID
    account_type: Literal["SAVINGS", "CHECKING"]
    currency: Literal["PEN", "USD"] = "PEN"


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID
    account_number: str
    account_type: str
    currency: str
    balance: Decimal
    status: str
    created_at: datetime
