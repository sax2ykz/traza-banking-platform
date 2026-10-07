"""Request/response validation independent of persistence and database driver."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AmountRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal('10000.00'), max_digits=7, decimal_places=2)
    currency: Literal['PEN', 'USD']
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$')


class OneAccountRequest(AmountRequest):
    account_id: UUID


class TransferRequest(AmountRequest):
    source_account_id: UUID
    target_account_id: UUID


class OperationResult(BaseModel):
    operation_id: UUID
    status: str
    operation_type: str
    amount: Decimal
    currency: str
    balances_after: dict[str, Decimal]
    replayed: bool


class MovementResult(BaseModel):
    id: UUID
    operation_id: UUID
    transaction_type: str
    direction: str
    amount: Decimal
    currency: str
    balance_after: Decimal
    created_at: datetime

class ThirdPartyBeneficiaryRequest(BaseModel):
    source_account_id: UUID
    target_account_number: str = Field(
        min_length=8,
        max_length=30,
        pattern=r'^[A-Za-z0-9]+$',
    )


class ThirdPartyBeneficiaryResult(BaseModel):
    holder_display: str
    account_last4: str
    account_type: str
    currency: str


class ThirdPartyTransferRequest(AmountRequest):
    source_account_id: UUID
    target_account_number: str = Field(
        min_length=8,
        max_length=30,
        pattern=r'^[A-Za-z0-9]+$',
    )


class InterbankTransferRequest(AmountRequest):
    source_account_id: UUID
    cci: str = Field(pattern=r'^\d{20}$')
    destination_bank: Literal[
        'BCP',
        'INTERBANK',
        'BBVA',
        'SCOTIABANK',
        'BANBIF',
        'BANCO_NACION',
    ]
