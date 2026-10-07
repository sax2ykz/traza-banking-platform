"""ADMIN endpoints for the BancoCloud Operational Copilot."""

from __future__ import annotations

import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import BadRequestError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.security import require_admin
from app.security_models import AppUser
from app.services.copilot_prompts import PROMPT_VERSION
from app.services.copilot_schemas import (
    CopilotAdminAnalysisResponse,
    CopilotHumanReviewRequest,
    CopilotHumanReviewResponse,
    OperationalExceptionContext,
)
from app.services.operational_copilot import (
    DEFAULT_MODEL,
    analyze_operational_exception,
)
from app.session import get_db


router = APIRouter(
    prefix="/api/v1/admin/copilot",
    tags=["Operational Copilot"],
)


def _one_or_none(result):
    row = result.mappings().first()
    return dict(row) if row is not None else None


def _rows(result):
    return [dict(row) for row in result.mappings().all()]


def _configured_model() -> str:
    return (
        os.getenv(
            "FOUNDRY_MODEL_NAME",
            DEFAULT_MODEL,
        ).strip()
        or DEFAULT_MODEL
    )


def _is_azure_guardrail_block(
    exc: BadRequestError,
) -> bool:
    message = str(exc).lower()

    return any(
        marker in message
        for marker in (
            "jailbreak",
            "content_filter",
            "contentfiltered",
        )
    )


def _build_dataops_context(
    *,
    run_id: UUID,
    db: Session,
) -> tuple[OperationalExceptionContext, dict]:
    """Build a minimized, server-controlled context for one DataOps exception."""

    run = _one_or_none(
        db.execute(
            text(
                """
                SELECT
                    run_id,
                    pipeline_name,
                    status,
                    started_at,
                    finished_at,
                    duration_seconds,
                    rows_extracted,
                    rows_accepted,
                    rows_quarantined,
                    quality_total,
                    quality_passed,
                    quality_failed,
                    quarantine_records,
                    publication_status,
                    is_current_gold,
                    published_at,
                    gold_row_count
                FROM analytics.vw_dataops_runs
                WHERE run_id = :run_id
                LIMIT 1
                """
            ),
            {
                "run_id": run_id,
            },
        )
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="La ejecución DataOps no existe.",
        )

    has_exception = (
        run["status"] != "SUCCEEDED"
        or int(run["quality_failed"] or 0) > 0
        or int(run["quarantine_records"] or 0) > 0
    )

    if not has_exception:
        raise HTTPException(
            status_code=409,
            detail=(
                "La ejecución DataOps no presenta "
                "una excepción que requiera análisis."
            ),
        )

    quarantine = _rows(
        db.execute(
            text(
                """
                SELECT
                    source_table,
                    rule_name,
                    reason,
                    rejected_records
                FROM analytics.vw_quarantine_summary
                WHERE run_id = :run_id
                ORDER BY
                    rejected_records DESC,
                    source_table,
                    rule_name
                LIMIT 10
                """
            ),
            {
                "run_id": run_id,
            },
        )
    )

    current_gold = _one_or_none(
        db.execute(
            text(
                """
                SELECT
                    batch_id,
                    source_run_id,
                    publication_status,
                    gold_row_count,
                    quality_gate_total,
                    quality_gate_passed,
                    rows_quarantined,
                    published_at
                FROM analytics.vw_current_gold_status
                LIMIT 1
                """
            )
        )
    )

    evidence: list[str] = [
        f"run_id={run['run_id']}",
        f"status={run['status']}",
        f"rows_extracted={run['rows_extracted']}",
        f"rows_accepted={run['rows_accepted']}",
        f"rows_quarantined={run['rows_quarantined']}",
        f"quality_total={run['quality_total']}",
        f"quality_passed={run['quality_passed']}",
        f"quality_failed={run['quality_failed']}",
        f"quarantine_records={run['quarantine_records']}",
        f"is_current_gold={run['is_current_gold']}",
    ]

    for item in quarantine:
        evidence.extend(
            [
                (
                    "quarantine_source_table="
                    f"{item['source_table']}"
                ),
                (
                    "quarantine_rule_name="
                    f"{item['rule_name']}"
                ),
                (
                    "quarantine_reason="
                    f"{item['reason']}"
                ),
                (
                    "quarantine_rejected_records="
                    f"{item['rejected_records']}"
                ),
            ]
        )

    if current_gold is not None:
        evidence.extend(
            [
                (
                    "current_gold_batch_id="
                    f"{current_gold['batch_id']}"
                ),
                (
                    "current_gold_source_run_id="
                    f"{current_gold['source_run_id']}"
                ),
                (
                    "current_gold_publication_status="
                    f"{current_gold['publication_status']}"
                ),
                (
                    "current_gold_gold_row_count="
                    f"{current_gold['gold_row_count']}"
                ),
                (
                    "current_gold_quality_gate_total="
                    f"{current_gold['quality_gate_total']}"
                ),
                (
                    "current_gold_quality_gate_passed="
                    f"{current_gold['quality_gate_passed']}"
                ),
                (
                    "current_gold_rows_quarantined="
                    f"{current_gold['rows_quarantined']}"
                ),
            ]
        )

    context = OperationalExceptionContext(
        exception_type=str(run["status"]),
        title=(
            "Ejecución DataOps con excepción "
            "operacional"
        ),
        description=(
            "El Operations Control Tower detectó "
            "una ejecución DataOps que requiere "
            "revisión. El contexto fue construido "
            "por FastAPI mediante una lista "
            "permitida de campos operacionales."
        ),
        evidence=evidence[:20],
        metadata={
            "source": (
                "BancoCloud Operations Control Tower"
            ),
            "environment": "academic_poc",
            "context_policy": "server_allowlist",
        },
    )

    return context, run


@router.post(
    "/dataops/{run_id}/analyze",
    response_model=CopilotAdminAnalysisResponse,
)
def analyze_dataops_run(
    run_id: UUID,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Analyze one existing DataOps exception using server-built context."""

    context, run = _build_dataops_context(
        run_id=run_id,
        db=db,
    )

    correlation_id = uuid4()
    configured_model = _configured_model()

    db.add(
        AuditEvent(
            correlation_id=correlation_id,
            actor_type="STAFF",
            action="GENAI_ANALYSIS_REQUESTED",
            entity_type="DATAOPS_RUN",
            entity_id=run_id,
            result="SUCCESS",
            details={
                "requested_by": str(admin.id),
                "requested_by_email": admin.email,
                "lifecycle_status": "REQUESTED",
                "exception_type": str(run["status"]),
                "evidence_count": len(
                    context.evidence
                ),
                "context_policy": "server_allowlist",
                "prompt_version": PROMPT_VERSION,
                "model": configured_model,
            },
        )
    )

    db.commit()

    try:
        result = analyze_operational_exception(
            context
        )

    except BadRequestError as exc:
        blocked = _is_azure_guardrail_block(
            exc
        )

        db.add(
            AuditEvent(
                correlation_id=correlation_id,
                actor_type="SYSTEM",
                action=(
                    "GENAI_ANALYSIS_BLOCKED"
                    if blocked
                    else "GENAI_ANALYSIS_FAILED"
                ),
                entity_type="DATAOPS_RUN",
                entity_id=run_id,
                result=(
                    "DENIED"
                    if blocked
                    else "FAILED"
                ),
                details={
                    "requested_by": str(admin.id),
                    "exception_type": str(
                        run["status"]
                    ),
                    "prompt_version": (
                        PROMPT_VERSION
                    ),
                    "model": configured_model,
                    "reason": (
                        "AZURE_CONTENT_SAFETY"
                        if blocked
                        else "AZURE_BAD_REQUEST"
                    ),
                    "human_review_required": True,
                },
            )
        )

        db.commit()

        raise HTTPException(
            status_code=422 if blocked else 502,
            detail=(
                "La solicitud fue bloqueada por "
                "los controles de seguridad de Azure."
                if blocked
                else (
                    "Microsoft Foundry rechazó "
                    "la solicitud del Copilot."
                )
            ),
        ) from exc

    except Exception as exc:
        db.add(
            AuditEvent(
                correlation_id=correlation_id,
                actor_type="SYSTEM",
                action="GENAI_ANALYSIS_FAILED",
                entity_type="DATAOPS_RUN",
                entity_id=run_id,
                result="FAILED",
                details={
                    "requested_by": str(admin.id),
                    "exception_type": str(
                        run["status"]
                    ),
                    "prompt_version": (
                        PROMPT_VERSION
                    ),
                    "model": configured_model,
                    "error_type": type(exc).__name__,
                    "human_review_required": True,
                },
            )
        )

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible completar el "
                "análisis del Operational Copilot."
            ),
        ) from exc

    db.add(
        AuditEvent(
            correlation_id=correlation_id,
            actor_type="SYSTEM",
            action="GENAI_ANALYSIS_COMPLETED",
            entity_type="DATAOPS_RUN",
            entity_id=run_id,
            result="SUCCESS",
            details={
                "requested_by": str(admin.id),
                "requested_by_email": admin.email,
                "exception_type": str(
                    run["status"]
                ),
                "context_policy": "server_allowlist",
                "prompt_version": (
                    result.prompt_version
                ),
                "model": result.model,
                "category": (
                    result.analysis.category
                ),
                "confidence": (
                    result.analysis.confidence
                ),
                "human_review_required": (
                    result.analysis
                    .human_review_required
                ),
                "analysis": (
                    result.analysis.model_dump(
                        mode="json"
                    )
                ),
            },
        )
    )

    db.commit()

    return CopilotAdminAnalysisResponse(
        correlation_id=correlation_id,
        status="COMPLETED",
        prompt_version=result.prompt_version,
        model=result.model,
        analysis=result.analysis,
        human_review_status="PENDING",
    )


@router.post(
    "/{correlation_id}/review",
    response_model=CopilotHumanReviewResponse,
)
def review_copilot_analysis(
    correlation_id: UUID,
    payload: CopilotHumanReviewRequest,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register the required human review for one Copilot analysis."""

    analysis_event = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.correlation_id
            == correlation_id,
            AuditEvent.action
            == "GENAI_ANALYSIS_COMPLETED",
        )
        .order_by(
            AuditEvent.occurred_at.desc()
        )
        .limit(1)
    )

    if analysis_event is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe un análisis completado "
                "para esta correlación."
            ),
        )

    existing_review = db.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.correlation_id
            == correlation_id,
            AuditEvent.action
            == "GENAI_HUMAN_REVIEWED",
        )
        .limit(1)
    )

    if existing_review is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Este análisis ya tiene una "
                "revisión humana registrada."
            ),
        )

    analysis_details = (
        analysis_event.details or {}
    )

    db.add(
        AuditEvent(
            correlation_id=correlation_id,
            actor_type="STAFF",
            action="GENAI_HUMAN_REVIEWED",
            entity_type=(
                analysis_event.entity_type
            ),
            entity_id=analysis_event.entity_id,
            result="SUCCESS",
            details={
                "reviewer_id": str(admin.id),
                "reviewer_email": admin.email,
                "reviewer_role": admin.role,
                "decision": payload.decision,
                "notes": payload.notes,
                "human_decision": True,
                "llm_decision": False,
                "prompt_version": (
                    analysis_details.get(
                        "prompt_version"
                    )
                ),
                "model": analysis_details.get(
                    "model"
                ),
            },
        )
    )

    db.commit()

    return CopilotHumanReviewResponse(
        correlation_id=correlation_id,
        decision=payload.decision,
        reviewed_by=admin.id,
        human_review_status="COMPLETED",
    )


@router.get("/history")
def copilot_history(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return completed Copilot analyses and their human-review state."""

    del admin

    analyses = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.action
            == "GENAI_ANALYSIS_COMPLETED"
        )
        .order_by(
            AuditEvent.occurred_at.desc()
        )
        .limit(limit)
    ).all()

    value = []

    for event in analyses:
        details = event.details or {}

        review = db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.correlation_id
                == event.correlation_id,
                AuditEvent.action
                == "GENAI_HUMAN_REVIEWED",
            )
            .order_by(
                AuditEvent.occurred_at.desc()
            )
            .limit(1)
        )

        human_review = None

        if review is not None:
            review_details = (
                review.details or {}
            )

            human_review = {
                "decision": (
                    review_details.get(
                        "decision"
                    )
                ),
                "reviewer_id": (
                    review_details.get(
                        "reviewer_id"
                    )
                ),
                "reviewer_email": (
                    review_details.get(
                        "reviewer_email"
                    )
                ),
                "notes": (
                    review_details.get(
                        "notes"
                    )
                ),
                "reviewed_at": (
                    review.occurred_at
                ),
            }

        value.append(
            {
                "correlation_id": str(
                    event.correlation_id
                ),
                "source_entity_type": (
                    event.entity_type
                ),
                "source_entity_id": (
                    str(event.entity_id)
                    if event.entity_id
                    else None
                ),
                "created_at": (
                    event.occurred_at
                ),
                "prompt_version": (
                    details.get(
                        "prompt_version"
                    )
                ),
                "model": details.get(
                    "model"
                ),
                "category": details.get(
                    "category"
                ),
                "confidence": details.get(
                    "confidence"
                ),
                "human_review_required": (
                    details.get(
                        "human_review_required",
                        True,
                    )
                ),
                "analysis": details.get(
                    "analysis"
                ),
                "human_review_status": (
                    "COMPLETED"
                    if review is not None
                    else "PENDING"
                ),
                "human_review": human_review,
            }
        )

    return {
        "value": value,
        "Count": len(value),
    }
