"""Synthetic RENIEC identity verification for BancoCloud onboarding.

Academic/local PoC only.
No request is sent to RENIEC or any real identity provider.
"""

from datetime import date, datetime, timedelta, timezone
from secrets import token_hex
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Customer
from app.onboarding_models import OnboardingExceptionCase
from app.reniec_models import (
    IdentityVerification,
    ReniecSimulatedRegistry,
)
from app.security import current_user
from app.security_models import AppUser
from app.services.onboarding_stp import evaluate_onboarding_stp
from app.services.reniec_rules import evaluate_identity
from app.session import get_db


router = APIRouter(
    prefix="/api/v1/onboarding/identity",
    tags=["Onboarding identity"],
)


class IdentityVerificationPayload(BaseModel):
    document_number: str = Field(
        min_length=8,
        max_length=8,
        pattern=r"^[0-9]{8}$",
    )
    birth_date: date


@router.post("/verify")
def verify_identity(
    payload: IdentityVerificationPayload,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role != "CUSTOMER" or user.customer_id is None:
        raise HTTPException(
            status_code=403,
            detail="Customer identity required",
        )

    customer = db.get(Customer, user.customer_id)

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    if customer.onboarding_status not in (
        "PENDING",
        "REVIEW_REQUIRED",
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Identity verification is only available "
                "during pending or exception-review onboarding"
            ),
        )

    active_exception = None

    if customer.onboarding_status == "REVIEW_REQUIRED":
        active_exception = db.scalar(
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

        if active_exception is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "REVIEW_REQUIRED customer has no "
                    "active onboarding exception"
                ),
            )

    registry = db.scalar(
        select(ReniecSimulatedRegistry).where(
            ReniecSimulatedRegistry.document_number
            == payload.document_number
        )
    )

    registry_document_status = (
        registry.document_status
        if registry is not None
        else None
    )

    (
        verification_result,
        matched_name,
        matched_birth_date,
    ) = evaluate_identity(
        customer_full_name=customer.full_name,
        claimed_birth_date=payload.birth_date,
        registry_full_name=(
            registry.full_name
            if registry is not None
            else None
        ),
        registry_birth_date=(
            registry.birth_date
            if registry is not None
            else None
        ),
        registry_document_status=registry_document_status,
    )

    # STP_V1 is deterministic. No LLM or probabilistic model may
    # decide VERIFIED.
    #
    # The current P1 implementation has no additional risk-alert
    # engine yet, so has_blocking_alerts remains explicitly False.
    # Any future alert engine must feed this rule before automatic
    # approval is allowed.
    stp_decision = evaluate_onboarding_stp(
        verification_result=verification_result,
        document_status=registry_document_status,
        matched_name=matched_name,
        matched_birth_date=matched_birth_date,
        evidence_complete=True,
        has_blocking_alerts=False,
    )

    evidence_ref = (
        "SIM-RENIEC-"
        + token_hex(8).upper()
    )

    verification = IdentityVerification(
        customer_id=customer.id,
        document_number=payload.document_number,
        claimed_full_name=customer.full_name,
        claimed_birth_date=payload.birth_date,
        result=verification_result,
        evidence_ref=evidence_ref,
        registry_document_status=registry_document_status,
        matched_name=matched_name,
        matched_birth_date=matched_birth_date,
        details={
            "synthetic": True,
            "source": "RENIEC_SIMULATOR",
            "real_external_request": False,
            "stp_rule_version": stp_decision.rule_version,
            "stp_decision": stp_decision.decision,
            "stp_reason": stp_decision.reason,
        },
    )

    db.add(verification)
    db.flush()

    exception_case = None
    previous_exception_case_id = None

    # A new verification supersedes the previous active exception.
    # Resolve it first so the partial unique index permits a new
    # active case for the same customer if review is still required.
    if active_exception is not None:
        previous_exception_case_id = str(active_exception.id)
        active_exception.status = "RESOLVED"
        active_exception.resolved_at = datetime.now(timezone.utc)
        db.flush()

    if stp_decision.decision == "VERIFIED":
        customer.onboarding_status = "VERIFIED"

    else:
        customer.onboarding_status = "REVIEW_REQUIRED"

        exception_case = OnboardingExceptionCase(
            customer_id=customer.id,
            identity_verification_id=verification.id,
            status="OPEN",
            reason=stp_decision.reason,
            priority=stp_decision.priority,
            severity=stp_decision.severity,
            rule_version=stp_decision.rule_version,
            sla_due_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=stp_decision.sla_hours)
            ),
        )

        db.add(exception_case)
        db.flush()

    # Preserve the original evidence-generation audit.
    db.add(
        AuditEvent(
            correlation_id=uuid4(),
            actor_type="CUSTOMER",
            action="SYNTHETIC_IDENTITY_VERIFICATION",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            result="SUCCESS",
            details={
                "synthetic": True,
                "source": "RENIEC_SIMULATOR",
                "verification_id": str(verification.id),
                "evidence_ref": evidence_ref,
                "verification_result": verification_result,
                "document_status": registry_document_status,
                "matched_name": matched_name,
                "matched_birth_date": matched_birth_date,
                "real_external_request": False,
            },
        )
    )

    # Separate audit event for the deterministic STP decision.
    db.add(
        AuditEvent(
            correlation_id=uuid4(),
            actor_type="SYSTEM",
            action="ONBOARDING_STP_DECISION",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            result="SUCCESS",
            details={
                "verification_id": str(verification.id),
                "evidence_ref": evidence_ref,
                "decision": stp_decision.decision,
                "reason": stp_decision.reason,
                "rule_version": stp_decision.rule_version,
                "automatic_verified": stp_decision.automatic,
                "human_review_required": (
                    stp_decision.decision
                    == "REVIEW_REQUIRED"
                ),
                "exception_case_id": (
                    str(exception_case.id)
                    if exception_case is not None
                    else None
                ),
                "previous_exception_case_id": (
                    previous_exception_case_id
                ),
                "reverification": (
                    previous_exception_case_id is not None
                ),
                "llm_decision": False,
                "synthetic": True,
            },
        )
    )

    db.commit()
    db.refresh(verification)

    return {
        "verification_id": str(verification.id),
        "customer_id": str(customer.id),
        "result": verification_result,
        "evidence_ref": evidence_ref,
        "document_status": registry_document_status,
        "matched_name": matched_name,
        "matched_birth_date": matched_birth_date,
        "verified_at": verification.verified_at,
        "onboarding_status": customer.onboarding_status,
        "stp": {
            "decision": stp_decision.decision,
            "reason": stp_decision.reason,
            "rule_version": stp_decision.rule_version,
            "automatic_verified": stp_decision.automatic,
            "human_review_required": (
                stp_decision.decision
                == "REVIEW_REQUIRED"
            ),
            "exception_case_id": (
                str(exception_case.id)
                if exception_case is not None
                else None
            ),
            "previous_exception_case_id": (
                previous_exception_case_id
            ),
            "reverification": (
                previous_exception_case_id is not None
            ),
            "llm_decision": False,
        },
        "synthetic": True,
        "source": "RENIEC_SIMULATOR",
    }
