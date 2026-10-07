"""Human-reviewed loan administration for the BancoCloud academic PoC.

The API does not perform autonomous credit scoring and no LLM can approve a
loan. A human ADMIN explicitly approves or rejects each pending application.
Approval schedules a future disbursement; it does not credit the account in the
same administrative action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Customer, Loan, LoanApplication, LoanInstallment
from app.security import require_admin
from app.security_models import AppUser
from app.services.loan_admin_schemas import (
    LoanAdminReview,
    LoanAdminReviewResult,
    PendingLoanApplication,
)
from app.services.loan_disbursement import (
    disbursement_timezone,
    next_business_disbursement_at,
)
from app.services.loan_rules import build_installment_schedule
from app.session import get_db

router = APIRouter(prefix="/api/v1/admin/loans", tags=["Administrative loan review"])


@router.get("/pending", response_model=list[PendingLoanApplication])
def pending_loan_applications(
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(LoanApplication, Customer, Account)
        .join(Customer, Customer.id == LoanApplication.customer_id)
        .outerjoin(Account, Account.id == LoanApplication.disbursement_account_id)
        .where(LoanApplication.status == "PENDING")
        .order_by(LoanApplication.requested_at, LoanApplication.id)
        .limit(100)
    ).all()

    return [
        PendingLoanApplication(
            application_id=application.id,
            customer_id=application.customer_id,
            customer_code=customer.customer_code,
            full_name=customer.full_name,
            requested_amount=application.requested_amount,
            currency=application.currency,
            term_months=application.term_months,
            purpose=application.purpose,
            disbursement_account_id=application.disbursement_account_id,
            disbursement_account_last4=(account.account_number[-4:] if account else None),
            status=application.status,
            human_review_required=application.human_review_required,
            requested_at=application.requested_at,
        )
        for application, customer, account in rows
    ]


@router.post("/{application_id}/review", response_model=LoanAdminReviewResult)
def review_loan_application(
    application_id: UUID,
    payload: LoanAdminReview,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    application = db.scalar(
        select(LoanApplication)
        .where(LoanApplication.id == application_id)
        .with_for_update()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found")
    if application.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending loan applications may be reviewed")

    now = datetime.now(timezone.utc)

    if payload.decision == "REJECTED":
        application.status = "REJECTED"
        application.reviewed_at = now

        db.add(
            AuditEvent(
                correlation_id=uuid4(),
                actor_type="STAFF",
                action="LOAN_APPLICATION_REVIEW",
                entity_type="LOAN_APPLICATION",
                entity_id=application.id,
                result="SUCCESS",
                details={
                    "reviewer_id": str(admin.id),
                    "decision": "REJECTED",
                    "human_decision": True,
                    "llm_decision": False,
                    "notes": payload.notes,
                },
            )
        )
        db.commit()
        return LoanAdminReviewResult(
            application_id=application.id,
            decision="REJECTED",
        )

    if payload.annual_rate is None:
        raise HTTPException(
            status_code=422,
            detail="annual_rate (TEA) is required for an approved application",
        )

    existing_loan = db.scalar(
        select(Loan).where(Loan.loan_application_id == application.id)
    )
    if existing_loan is not None:
        raise HTTPException(status_code=409, detail="A loan already exists for this application")

    if application.disbursement_account_id is None:
        raise HTTPException(
            status_code=409,
            detail="A disbursement account must be selected before approval",
        )

    disbursement_account = db.scalar(
        select(Account)
        .where(Account.id == application.disbursement_account_id)
        .with_for_update()
    )
    if disbursement_account is None:
        raise HTTPException(status_code=404, detail="Disbursement account not found")
    if disbursement_account.customer_id != application.customer_id:
        raise HTTPException(status_code=409, detail="Disbursement account ownership mismatch")
    if disbursement_account.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Disbursement account is not active")
    if disbursement_account.currency != application.currency:
        raise HTTPException(status_code=409, detail="Disbursement account currency mismatch")

    scheduled_at = next_business_disbursement_at(now)
    schedule_base_date = scheduled_at.astimezone(disbursement_timezone()).date()

    loan = Loan(
        customer_id=application.customer_id,
        principal=application.requested_amount,
        annual_rate=payload.annual_rate,
        term_months=application.term_months,
        status="APPROVED",
        requested_at=application.requested_at,
        loan_application_id=application.id,
        approved_at=now,
        approved_by_user_id=admin.id,
        disbursement_account_id=disbursement_account.id,
        disbursement_status="SCHEDULED",
        scheduled_disbursement_at=scheduled_at,
    )
    db.add(loan)
    db.flush()

    schedule = build_installment_schedule(
        principal=application.requested_amount,
        annual_effective_rate_percent=payload.annual_rate,
        term_months=application.term_months,
        first_due_from=schedule_base_date,
    )
    for number, due_date, due_amount in schedule:
        db.add(
            LoanInstallment(
                loan_id=loan.id,
                installment_number=number,
                due_date=due_date,
                due_amount=due_amount,
                paid_amount=0,
                status="SCHEDULED",
            )
        )

    application.status = "APPROVED"
    application.reviewed_at = now

    correlation_id = uuid4()
    db.add_all(
        [
            AuditEvent(
                correlation_id=correlation_id,
                actor_type="STAFF",
                action="LOAN_APPLICATION_REVIEW",
                entity_type="LOAN_APPLICATION",
                entity_id=application.id,
                result="SUCCESS",
                details={
                    "reviewer_id": str(admin.id),
                    "decision": "APPROVED",
                    "human_decision": True,
                    "llm_decision": False,
                    "loan_id": str(loan.id),
                    "tea_percent": str(payload.annual_rate),
                    "installments_created": application.term_months,
                    "notes": payload.notes,
                    "disbursement_status": "SCHEDULED",
                    "scheduled_disbursement_at": scheduled_at.isoformat(),
                    "disbursement_account_id": str(disbursement_account.id),
                    "disbursement_account_last4": disbursement_account.account_number[-4:],
                },
            ),
            AuditEvent(
                correlation_id=correlation_id,
                actor_type="SYSTEM",
                action="LOAN_DISBURSEMENT_SCHEDULED",
                entity_type="LOAN",
                entity_id=loan.id,
                result="SUCCESS",
                details={
                    "loan_id": str(loan.id),
                    "approved_by": str(admin.id),
                    "scheduled_disbursement_at": scheduled_at.isoformat(),
                    "disbursement_account_id": str(disbursement_account.id),
                    "account_last4": disbursement_account.account_number[-4:],
                },
            ),
        ]
    )
    db.commit()

    return LoanAdminReviewResult(
        application_id=application.id,
        decision="APPROVED",
        loan_id=loan.id,
        installments_created=application.term_months,
        annual_rate=payload.annual_rate,
        disbursement_status="SCHEDULED",
        scheduled_disbursement_at=scheduled_at,
        disbursement_account_last4=disbursement_account.account_number[-4:],
    )
