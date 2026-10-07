"""Synthetic customers and pending onboarding. Local-only; auth comes before cloud publishing."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Customer
from app.schemas import AccountRead, CustomerCreate, CustomerRead
from app.session import get_db
from app.security import current_user, require_admin, verify_customer_access
from app.security_models import AppUser

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, admin: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    existing = db.scalar(select(Customer.id).where(or_(
        Customer.customer_code == payload.customer_code,
        Customer.email == payload.email,
    )))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Customer code or email already exists")

    customer = Customer(**payload.model_dump())
    db.add(customer)
    try:
        db.commit()
        db.refresh(customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer code or email already exists")
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: UUID, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    verify_customer_access(user, customer_id)
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers(offset: int = 0, limit: int = 20, admin: AppUser = Depends(require_admin), db: Session = Depends(get_db)):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination")
    return db.scalars(select(Customer).order_by(Customer.created_at, Customer.id).offset(offset).limit(limit)).all()

@router.get(
    "/{customer_id}/accounts",
    response_model=list[AccountRead],
)
def customer_accounts(
    customer_id: UUID,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    verify_customer_access(user, customer_id)

    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    return db.scalars(
        select(Account)
        .where(Account.customer_id == customer_id)
        .order_by(Account.created_at.desc(), Account.id.desc())
    ).all()