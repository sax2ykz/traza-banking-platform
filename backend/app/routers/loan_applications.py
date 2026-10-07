"""Submit loan requests ONLY. No auto-approval, risk model or disbursement."""

import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Customer, LoanApplication
from app.services.cards_loans_schemas import LoanApplicationCreate, LoanApplicationRead
from app.session import get_db
from app.security import current_user, verify_customer_access
from app.security_models import AppUser

router = APIRouter(prefix='/api/v1', tags=['Loan applications (synthetic)'])


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

@router.post('/loan-applications', response_model=LoanApplicationRead,
             status_code=status.HTTP_201_CREATED)
def submit_loan_application(payload: LoanApplicationCreate, request: Request,
                            user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    verify_customer_access(user, payload.customer_id)
    require_local(request)
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail='Customer not found')
    if customer.onboarding_status != 'VERIFIED':
        raise HTTPException(status_code=409, detail='Verified onboarding required')

    disbursement_account = db.get(Account, payload.disbursement_account_id)
    if disbursement_account is None:
        raise HTTPException(status_code=404, detail='Disbursement account not found')
    if disbursement_account.customer_id != customer.id:
        raise HTTPException(status_code=403, detail='Disbursement account does not belong to customer')
    if disbursement_account.status != 'ACTIVE':
        raise HTTPException(status_code=409, detail='Disbursement account is not active')
    if disbursement_account.currency != payload.currency:
        raise HTTPException(status_code=409, detail='Disbursement account currency mismatch')

    application = LoanApplication(
        customer_id=customer.id, requested_amount=payload.requested_amount,
        currency=payload.currency, term_months=payload.term_months,
        purpose=payload.purpose,
        disbursement_account_id=disbursement_account.id,
        status='PENDING', human_review_required=True,
    )
    db.add(application)
    db.flush()
    db.add(AuditEvent(
        correlation_id=uuid4(), actor_type='SERVICE',
        action='SYNTHETIC_LOAN_APPLICATION_SUBMITTED',
        entity_type='LOAN_APPLICATION', entity_id=application.id, result='SUCCESS',
        details={
            'synthetic': True,
            'human_review_required': True,
            'disbursement_account_id': str(disbursement_account.id),
            'disbursement_account_last4': disbursement_account.account_number[-4:],
        },
    ))
    db.commit()
    db.refresh(application)
    return application


@router.get('/loan-applications/{application_id}', response_model=LoanApplicationRead)
def get_loan_application(application_id: UUID, request: Request, user: AppUser = Depends(current_user), db: Session = Depends(get_db)):
    require_local(request)
    application = db.get(LoanApplication, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail='Loan application not found')
    verify_customer_access(user, application.customer_id)
    return application


@router.get('/customers/{customer_id}/loan-applications', response_model=list[LoanApplicationRead])
def customer_loan_applications(customer_id: UUID, request: Request, user: AppUser = Depends(current_user),
                               db: Session = Depends(get_db)):
    verify_customer_access(user, customer_id)
    require_local(request)
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail='Customer not found')
    return db.scalars(select(LoanApplication).where(LoanApplication.customer_id == customer_id)
                      .order_by(LoanApplication.requested_at.desc(), LoanApplication.id.desc())).all()
