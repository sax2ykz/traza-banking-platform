"""Customer-facing read-only loan and installment views."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Customer, Loan, LoanApplication, LoanInstallment
from app.security import current_user, verify_customer_access
from app.security_models import AppUser
from app.services.customer_loans_schemas import CustomerLoanSummary, LoanInstallmentDetail
from app.session import get_db

router = APIRouter(prefix="/api/v1", tags=["Customer loans"])


def _outstanding(due: Decimal, paid: Decimal) -> Decimal:
    value = due - paid
    return value if value > Decimal("0.00") else Decimal("0.00")


@router.get("/customers/{customer_id}/loans", response_model=list[CustomerLoanSummary])
def customer_loans(
    customer_id: UUID,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    verify_customer_access(user, customer_id)

    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    loans = db.scalars(
        select(Loan)
        .where(Loan.customer_id == customer_id)
        .order_by(Loan.requested_at.desc(), Loan.id.desc())
    ).all()

    result: list[CustomerLoanSummary] = []

    for loan in loans:
        installments = db.scalars(
            select(LoanInstallment)
            .where(LoanInstallment.loan_id == loan.id)
            .order_by(LoanInstallment.installment_number)
        ).all()

        application = (
            db.get(LoanApplication, loan.loan_application_id)
            if loan.loan_application_id is not None
            else None
        )
        currency = application.currency if application is not None else "UNKNOWN"

        total_scheduled = sum(
            (Decimal(str(item.due_amount)) for item in installments),
            Decimal("0.00"),
        )
        total_paid = sum(
            (Decimal(str(item.paid_amount)) for item in installments),
            Decimal("0.00"),
        )
        outstanding = sum(
            (
                _outstanding(
                    Decimal(str(item.due_amount)),
                    Decimal(str(item.paid_amount)),
                )
                for item in installments
            ),
            Decimal("0.00"),
        )

        next_installment = next(
            (
                item
                for item in installments
                if _outstanding(
                    Decimal(str(item.due_amount)),
                    Decimal(str(item.paid_amount)),
                ) > Decimal("0.00")
            ),
            None,
        )

        disbursement_account = (
            db.get(Account, loan.disbursement_account_id)
            if loan.disbursement_account_id is not None
            else None
        )

        result.append(
            CustomerLoanSummary(
                id=loan.id,
                customer_id=loan.customer_id,
                loan_application_id=loan.loan_application_id,
                principal=loan.principal,
                currency=currency,
                annual_rate=loan.annual_rate,
                term_months=loan.term_months,
                status=loan.status,
                requested_at=loan.requested_at,
                approved_at=loan.approved_at,
                disbursement_status=loan.disbursement_status,
                scheduled_disbursement_at=loan.scheduled_disbursement_at,
                disbursed_at=loan.disbursed_at,
                disbursement_operation_id=loan.disbursement_operation_id,
                disbursement_account_id=loan.disbursement_account_id,
                disbursement_account_last4=(
                    disbursement_account.account_number[-4:]
                    if disbursement_account is not None
                    else None
                ),
                installment_count=len(installments),
                installment_amount=installments[0].due_amount if installments else None,
                total_scheduled=total_scheduled,
                total_paid=total_paid,
                outstanding_amount=outstanding,
                next_due_date=next_installment.due_date if next_installment else None,
                next_due_amount=(
                    _outstanding(
                        Decimal(str(next_installment.due_amount)),
                        Decimal(str(next_installment.paid_amount)),
                    )
                    if next_installment
                    else None
                ),
            )
        )

    return result


@router.get("/loans/{loan_id}/installments", response_model=list[LoanInstallmentDetail])
def loan_installments(
    loan_id: UUID,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")

    verify_customer_access(user, loan.customer_id)

    installments = db.scalars(
        select(LoanInstallment)
        .where(LoanInstallment.loan_id == loan.id)
        .order_by(LoanInstallment.installment_number)
    ).all()

    return [
        LoanInstallmentDetail(
            id=item.id,
            loan_id=item.loan_id,
            installment_number=item.installment_number,
            due_date=item.due_date,
            due_amount=item.due_amount,
            paid_amount=item.paid_amount,
            outstanding_amount=_outstanding(
                Decimal(str(item.due_amount)),
                Decimal(str(item.paid_amount)),
            ),
            status=item.status,
        )
        for item in installments
    ]
