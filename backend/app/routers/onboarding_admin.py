"""Human review for STP onboarding exceptions.

Academic/local PoC only.
Normal low-risk onboarding is handled by deterministic STP rules.
ADMIN intervention is reserved for REVIEW_REQUIRED exceptions.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Customer
from app.onboarding_models import OnboardingExceptionCase
from app.reniec_models import IdentityVerification
from app.security import require_admin
from app.security_models import AppUser, OnboardingReview
from app.session import get_db


router = APIRouter(
    prefix="/api/v1/admin/onboarding",
    tags=["Administrative onboarding"],
)


class ReviewPayload(BaseModel):
    decision: Literal["VERIFIED", "REJECTED"]

    evidence_ref: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^SIM-[A-Za-z0-9_-]{4,76}$",
    )

    document_checked: bool
    data_consistent: bool

    notes: str = Field(
        default="",
        max_length=250,
    )


class AssignPayload(BaseModel):
    assignee_user_id: UUID | None = None


@router.get("/pending")
def pending(
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    priority_order = case(
        (OnboardingExceptionCase.priority == "HIGH", 0),
        (OnboardingExceptionCase.priority == "MEDIUM", 1),
        else_=2,
    )

    exception_cases = db.scalars(
        select(OnboardingExceptionCase)
        .where(
            OnboardingExceptionCase.status.in_(
                ("OPEN", "ASSIGNED")
            )
        )
        .order_by(
            priority_order,
            OnboardingExceptionCase.sla_due_at,
            OnboardingExceptionCase.created_at,
        )
        .limit(50)
    ).all()

    result = []

    for exception_case in exception_cases:
        customer = db.get(
            Customer,
            exception_case.customer_id,
        )

        if customer is None:
            continue

        if customer.onboarding_status != "REVIEW_REQUIRED":
            continue

        identity_verification = db.get(
            IdentityVerification,
            exception_case.identity_verification_id,
        )

        result.append(
            {
                # Existing frontend contract.
                "customer_id": str(customer.id),
                "customer_code": customer.customer_code,
                "full_name": customer.full_name,
                "onboarding_status": customer.onboarding_status,
                "identity_verification": (
                    {
                        "result": identity_verification.result,
                        "evidence_ref": (
                            identity_verification.evidence_ref
                        ),
                        "verified_at": (
                            identity_verification.verified_at
                        ),
                    }
                    if identity_verification is not None
                    else None
                ),

                # Additional STP queue metadata.
                # Existing frontend clients may safely ignore it.
                "exception_case": {
                    "id": str(exception_case.id),
                    "status": exception_case.status,
                    "reason": exception_case.reason,
                    "priority": exception_case.priority,
                    "severity": exception_case.severity,
                    "rule_version": exception_case.rule_version,
                    "assigned_to": (
                        str(exception_case.assigned_to)
                        if exception_case.assigned_to is not None
                        else None
                    ),
                    "created_at": exception_case.created_at,
                    "assigned_at": exception_case.assigned_at,
                    "sla_due_at": exception_case.sla_due_at,
                    "resolved_at": exception_case.resolved_at,
                },
            }
        )

    return result


@router.post("/{customer_id}/assign")
def assign_exception(
    customer_id: UUID,
    payload: AssignPayload,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    customer = db.scalar(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if customer.onboarding_status != "REVIEW_REQUIRED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only REVIEW_REQUIRED records "
                "may be assigned"
            ),
        )

    exception_case = db.scalar(
        select(OnboardingExceptionCase)
        .where(
            OnboardingExceptionCase.customer_id
            == customer.id,
            OnboardingExceptionCase.status.in_(
                ("OPEN", "ASSIGNED")
            ),
        )
        .order_by(
            OnboardingExceptionCase.created_at.desc(),
            OnboardingExceptionCase.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )

    if exception_case is None:
        raise HTTPException(
            status_code=409,
            detail="No active onboarding exception exists",
        )

    assignee_id = (
        payload.assignee_user_id
        if payload.assignee_user_id is not None
        else admin.id
    )

    assignee = db.get(AppUser, assignee_id)

    if (
        assignee is None
        or not assignee.active
        or assignee.role != "ADMIN"
    ):
        raise HTTPException(
            status_code=422,
            detail="Assignee must be an active ADMIN",
        )

    previous_assigned_to = exception_case.assigned_to

    if (
        exception_case.status == "ASSIGNED"
        and previous_assigned_to == assignee.id
    ):
        return {
            "customer_id": str(customer.id),
            "exception_case_id": str(exception_case.id),
            "status": exception_case.status,
            "assigned_to": str(exception_case.assigned_to),
            "assigned_at": exception_case.assigned_at,
            "reassigned": False,
            "rule_version": exception_case.rule_version,
        }

    assigned_at = datetime.now(timezone.utc)

    was_reassignment = (
        exception_case.status == "ASSIGNED"
        and previous_assigned_to is not None
    )

    exception_case.status = "ASSIGNED"
    exception_case.assigned_to = assignee.id
    exception_case.assigned_at = assigned_at
    exception_case.resolved_at = None

    db.add(
        AuditEvent(
            correlation_id=uuid4(),
            actor_type="STAFF",
            action=(
                "ONBOARDING_EXCEPTION_REASSIGNED"
                if was_reassignment
                else "ONBOARDING_EXCEPTION_ASSIGNED"
            ),
            entity_type="CUSTOMER",
            entity_id=customer.id,
            result="SUCCESS",
            details={
                "exception_case_id": str(exception_case.id),
                "performed_by": str(admin.id),
                "assigned_to": str(assignee.id),
                "previous_assigned_to": (
                    str(previous_assigned_to)
                    if previous_assigned_to is not None
                    else None
                ),
                "reason": exception_case.reason,
                "priority": exception_case.priority,
                "severity": exception_case.severity,
                "rule_version": exception_case.rule_version,
                "reassigned": was_reassignment,
                "human_action": True,
                "llm_decision": False,
            },
        )
    )

    db.commit()

    return {
        "customer_id": str(customer.id),
        "exception_case_id": str(exception_case.id),
        "status": "ASSIGNED",
        "assigned_to": str(assignee.id),
        "assigned_at": assigned_at,
        "previous_assigned_to": (
            str(previous_assigned_to)
            if previous_assigned_to is not None
            else None
        ),
        "reassigned": was_reassignment,
        "rule_version": exception_case.rule_version,
    }


@router.post("/{customer_id}/review")
def review(
    customer_id: UUID,
    payload: ReviewPayload,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    customer = db.scalar(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if customer.onboarding_status != "REVIEW_REQUIRED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Only REVIEW_REQUIRED records "
                "may be manually reviewed"
            ),
        )

    exception_case = db.scalar(
        select(OnboardingExceptionCase)
        .where(
            OnboardingExceptionCase.customer_id
            == customer.id,
            OnboardingExceptionCase.status.in_(
                ("OPEN", "ASSIGNED")
            ),
        )
        .order_by(
            OnboardingExceptionCase.created_at.desc(),
            OnboardingExceptionCase.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )

    if exception_case is None:
        raise HTTPException(
            status_code=409,
            detail="No active onboarding exception exists",
        )

    identity_verification = db.scalar(
        select(IdentityVerification)
        .where(
            IdentityVerification.evidence_ref
            == payload.evidence_ref
        )
    )

    if identity_verification is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "A valid synthetic RENIEC evidence "
                "reference is required"
            ),
        )

    if identity_verification.customer_id != customer.id:
        raise HTTPException(
            status_code=422,
            detail=(
                "RENIEC evidence does not belong "
                "to this customer"
            ),
        )

    if (
        identity_verification.id
        != exception_case.identity_verification_id
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "RENIEC evidence does not match "
                "the active exception case"
            ),
        )

    if payload.decision == "VERIFIED":
        if not (
            payload.document_checked
            and payload.data_consistent
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Both synthetic checklist checks "
                    "are required to approve"
                ),
            )

        # Human approval still requires valid current MATCH evidence.
        # MISMATCH / NOT_CURRENT / NOT_FOUND must receive new valid
        # evidence before they can become VERIFIED.
        if not (
            identity_verification.result == "MATCH"
            and identity_verification.registry_document_status
            == "CURRENT"
            and identity_verification.matched_name
            and identity_verification.matched_birth_date
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Human approval requires a current "
                    "RENIEC MATCH with consistent data"
                ),
            )

    record = OnboardingReview(
        customer_id=customer.id,
        reviewer_id=admin.id,
        decision=payload.decision,
        evidence_ref=payload.evidence_ref,
        document_checked=payload.document_checked,
        data_consistent=payload.data_consistent,
        notes=payload.notes,
    )

    db.add(record)
    db.flush()

    customer.onboarding_status = payload.decision

    resolved_at = datetime.now(timezone.utc)

    exception_case.status = "RESOLVED"
    exception_case.resolved_at = resolved_at

    db.add(
        AuditEvent(
            correlation_id=uuid4(),
            actor_type="STAFF",
            action="SYNTHETIC_ONBOARDING_REVIEW",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            result="SUCCESS",
            details={
                "review_id": str(record.id),
                "reviewer_id": str(admin.id),
                "decision": payload.decision,
                "synthetic": True,
                "evidence_reference_only": payload.evidence_ref,
                "reniec_verification_id": str(
                    identity_verification.id
                ),
                "reniec_result": identity_verification.result,
                "exception_case_id": str(exception_case.id),
                "exception_reason": exception_case.reason,
                "rule_version": exception_case.rule_version,
                "human_decision": True,
                "llm_decision": False,
            },
        )
    )

    db.commit()

    return {
        # Existing frontend contract.
        "customer_id": str(customer.id),
        "onboarding_status": payload.decision,
        "review_id": str(record.id),
        "evidence_ref": payload.evidence_ref,
        "reniec_result": identity_verification.result,
        "human_decision": True,
        "synthetic": True,

        # Additional traceability.
        "exception_case_id": str(exception_case.id),
        "exception_status": "RESOLVED",
        "rule_version": exception_case.rule_version,
        "llm_decision": False,
    }
