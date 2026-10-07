"""Issue synthetic card references (NO PAN or real cards). Local-only until auth exists."""

import os
from secrets import randbelow, token_hex
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Card, Customer
from app.services.cards_loans_schemas import CardCreate, CardRead
from app.session import get_db
from app.security import current_user, verify_customer_access
from app.security_models import AppUser

router = APIRouter(prefix='/api/v1', tags=['Cards (synthetic)'])


def require_local(request: Request) -> None:
    # Local development remains restricted to loopback.
    # Azure demo is public but still protected by JWT, roles and ownership checks.
    app_env = os.getenv("APP_ENV", "local").strip().lower()

    if app_env == "azure":
        return

    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1", "testclient"}
    ):
        raise HTTPException(
            status_code=403,
            detail="Development-only endpoint",
        )

@router.post('/cards', response_model=CardRead, status_code=status.HTTP_201_CREATED)
def issue_synthetic_card(payload: CardCreate, request: Request, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    require_local(request)
    account = db.scalar(select(Account).where(Account.id == payload.account_id).with_for_update())
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    verify_customer_access(user, account.customer_id)
    if account.status != 'ACTIVE':
        raise HTTPException(status_code=409, detail='Account must be active')
    customer = db.get(Customer, account.customer_id)
    if customer is None or customer.onboarding_status != 'VERIFIED':
        raise HTTPException(status_code=409, detail='Verified onboarding required')

    # Never generate/store a real PAN, CVV, expiry or cardholder payment credential.
    card = Card(
        account_id=account.id,
        card_reference='BC-SIM-' + token_hex(10).upper(),
        last_four=f'{randbelow(10000):04d}',
        status='ACTIVE',
    )
    db.add(card)
    db.flush()
    db.add(AuditEvent(
        correlation_id=uuid4(), actor_type='SERVICE', action='SYNTHETIC_CARD_ISSUED',
        entity_type='CARD', entity_id=card.id, result='SUCCESS',
        details={'synthetic': True, 'real_payment_card': False},
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Synthetic card creation conflict')
    db.refresh(card)
    return card


@router.get('/cards/{card_id}', response_model=CardRead)
def get_card(card_id: UUID, request: Request, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    require_local(request)
    card = db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail='Card not found')
    account = db.get(Account, card.account_id)
    verify_customer_access(user, account.customer_id)
    return card


@router.get('/accounts/{account_id}/cards', response_model=list[CardRead])
def account_cards(account_id: UUID, request: Request, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    require_local(request)
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    verify_customer_access(user, account.customer_id)
    return db.scalars(select(Card).where(Card.account_id == account_id)
                      .order_by(Card.created_at.desc(), Card.id.desc())).all()
