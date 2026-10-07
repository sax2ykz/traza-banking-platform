"""Deterministic Straight-Through Processing rules for onboarding.

STP_V1 never uses an LLM or probabilistic model to approve identity.
Ambiguous, incomplete or exceptional evidence fails closed to
REVIEW_REQUIRED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RULE_VERSION = "STP_V1"

OnboardingDecision = Literal[
    "VERIFIED",
    "REVIEW_REQUIRED",
]

Priority = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
]

Severity = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
]


@dataclass(frozen=True)
class StpDecision:
    decision: OnboardingDecision
    reason: str
    automatic: bool
    rule_version: str
    priority: Priority
    severity: Severity
    sla_hours: int


def _review(
    *,
    reason: str,
    priority: Priority,
    severity: Severity,
    sla_hours: int,
) -> StpDecision:
    return StpDecision(
        decision="REVIEW_REQUIRED",
        reason=reason,
        automatic=False,
        rule_version=RULE_VERSION,
        priority=priority,
        severity=severity,
        sla_hours=sla_hours,
    )


def evaluate_onboarding_stp(
    *,
    verification_result: str,
    document_status: str | None,
    matched_name: bool,
    matched_birth_date: bool,
    evidence_complete: bool = True,
    has_blocking_alerts: bool = False,
) -> StpDecision:
    """Evaluate the deterministic STP_V1 onboarding rules.

    Automatic VERIFIED requires every low-risk condition to be true.
    Any missing evidence, alert or non-MATCH result is escalated to
    human review.
    """

    # Fail closed if there is not enough evidence to decide safely.
    if not evidence_complete:
        return _review(
            reason="INSUFFICIENT_EVIDENCE",
            priority="HIGH",
            severity="HIGH",
            sla_hours=4,
        )

    # A business/risk alert always requires human review.
    if has_blocking_alerts:
        return _review(
            reason="BUSINESS_RULE_ALERT",
            priority="HIGH",
            severity="HIGH",
            sla_hours=4,
        )

    if verification_result == "MISMATCH":
        return _review(
            reason="IDENTITY_MISMATCH",
            priority="HIGH",
            severity="HIGH",
            sla_hours=4,
        )

    if verification_result == "NOT_CURRENT":
        return _review(
            reason="DOCUMENT_NOT_CURRENT",
            priority="MEDIUM",
            severity="MEDIUM",
            sla_hours=8,
        )

    if verification_result == "NOT_FOUND":
        return _review(
            reason="IDENTITY_NOT_FOUND",
            priority="MEDIUM",
            severity="MEDIUM",
            sla_hours=8,
        )

    # Only the complete, internally consistent MATCH path may use STP.
    if (
        verification_result == "MATCH"
        and document_status == "CURRENT"
        and matched_name
        and matched_birth_date
    ):
        return StpDecision(
            decision="VERIFIED",
            reason="LOW_RISK_IDENTITY_MATCH",
            automatic=True,
            rule_version=RULE_VERSION,
            priority="LOW",
            severity="LOW",
            sla_hours=0,
        )

    # Unknown/inconsistent states never become VERIFIED.
    return _review(
        reason="INSUFFICIENT_EVIDENCE",
        priority="HIGH",
        severity="HIGH",
        sla_hours=4,
    )
