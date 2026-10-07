"""Accounts cannot be opened before onboarding verification. No free balance input."""
from secrets import token_hex
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Customer
from app.schemas import AccountCreate, AccountRead
from app.session import get_db
from app.security import current_user, verify_customer_access
from app.security_models import AppUser

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    verify_customer_access(user, payload.customer_id)
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.onboarding_status != "VERIFIED":
        raise HTTPException(status_code=409, detail="Onboarding verification required")
    # Locally generated, synthetic, NOT a real banking account number.
    account = Account(
        customer_id=payload.customer_id,
        account_number="BC" + token_hex(10).upper(),
        account_type=payload.account_type,
        currency=payload.currency,
    )
    db.add(account)
    try:
        db.commit()
        db.refresh(account)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account creation conflict")
    return account


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: UUID, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    verify_customer_access(user, account.customer_id)
    return account
