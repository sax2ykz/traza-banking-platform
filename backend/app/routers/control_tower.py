"""Read-only Operations Control Tower for the BancoCloud local academic PoC.

Provides administrative visibility over:

- transactional operations;
- ledger and movements;
- audit events;
- human administrative decisions;
- DataOps executions;
- Quality Gates;
- Quarantine;
- current published Gold batch.

This router is intentionally read-only. Operational actions such as running
pipelines or injecting controlled failures are implemented separately.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.security import require_admin
from app.security_models import AppUser
from app.session import get_db

def _run_bancocloud_pipeline(
    *,
    controlled_quality_test: bool,
) -> UUID:
    """Load and execute the existing BancoCloud DataOps pipeline.

    The backend directory is normally the FastAPI working directory,
    while dataops/ lives at the project root. The project root is added
    explicitly so the existing pipeline can be reused without duplicating
    DataOps logic inside the API.
    """

    project_root = Path(__file__).resolve().parents[3]

    project_root_text = str(project_root)

    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

    from dataops.pipeline_core import run_pipeline

    return run_pipeline(
        controlled_quality_test=controlled_quality_test,
    )


router = APIRouter(
    prefix="/api/v1/admin/control-tower",
    tags=["Operations Control Tower"],
)


def _one_or_none(result):
    row = result.mappings().first()
    return dict(row) if row is not None else None


def _rows(result):
    return [dict(row) for row in result.mappings().all()]


@router.get("/overview")
def control_tower_overview(
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """High-level operational status for the Control Tower."""

    latest_run = _one_or_none(
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
                    gold_row_count,
                    error_message
                FROM analytics.vw_dataops_runs
                ORDER BY started_at DESC NULLS LAST
                LIMIT 1
                """
            )
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
                    published_at,
                    pipeline_name,
                    pipeline_status,
                    rows_extracted,
                    rows_accepted
                FROM analytics.vw_current_gold_status
                LIMIT 1
                """
            )
        )
    )

    counts = _one_or_none(
        db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.banking_operations)
                        AS banking_operations,
                    (SELECT COUNT(*) FROM public.audit_events)
                        AS audit_events,
                    (SELECT COUNT(*) FROM public.ledger_entries)
                        AS ledger_entries,
                    (SELECT COUNT(*) FROM public.transactions)
                        AS transactions,
                    (SELECT COUNT(*) FROM quarantine.rejected_records)
                        AS quarantine_records,
                    (
                        SELECT COUNT(*)
                        FROM public.customers
                        WHERE onboarding_status = 'PENDING'
                    ) AS pending_onboarding,
                    (
                        SELECT COUNT(*)
                        FROM public.loan_applications
                        WHERE status = 'PENDING'
                    ) AS pending_loans
                """
            )
        )
    )

    return {
        "api": "UP",
        "postgresql": "UP",
        "admin": {
            "id": str(admin.id),
            "email": admin.email,
            "role": admin.role,
        },
        "latest_dataops_run": latest_run,
        "current_gold": current_gold,
        "counts": counts,
    }


@router.get("/operations")
def control_tower_operations(
    limit: int = Query(default=20, ge=1, le=100),
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recent banking operations with movement/ledger/audit context."""

    rows = db.execute(
        text(
            """
            SELECT
                bo.id AS operation_id,
                bo.operation_type,
                bo.status,
                bo.amount,
                bo.currency,
                bo.source_account_id,
                bo.target_account_id,
                bo.created_at,
                bo.completed_at,

                source_customer.customer_code
                    AS source_customer_code,

                target_customer.customer_code
                    AS target_customer_code,

                COUNT(DISTINCT tx.id)
                    AS transaction_count,

                COUNT(DISTINCT le.id)
                    AS ledger_entry_count,

                audit.correlation_id,

                audit.actor_type AS actor_type,

                audit.details ->> 'actor_id'
                    AS actor_id,

                actor.email
                    AS actor_email

            FROM public.banking_operations bo

            LEFT JOIN public.accounts source_account
                ON source_account.id = bo.source_account_id

            LEFT JOIN public.customers source_customer
                ON source_customer.id = source_account.customer_id

            LEFT JOIN public.accounts target_account
                ON target_account.id = bo.target_account_id

            LEFT JOIN public.customers target_customer
                ON target_customer.id = target_account.customer_id

            LEFT JOIN public.transactions tx
                ON tx.operation_id = bo.id

            LEFT JOIN public.ledger_entries le
                ON le.operation_id = bo.id

            LEFT JOIN public.audit_events audit
                ON audit.entity_type = 'BANKING_OPERATION'
               AND audit.entity_id = bo.id
               AND audit.action IN ('FINANCIAL_OPERATION', 'SYNTHETIC_FINANCIAL_OPERATION')

            LEFT JOIN public.app_users actor
                ON actor.id::text = audit.details ->> 'actor_id'

            GROUP BY
                bo.id,
                bo.operation_type,
                bo.status,
                bo.amount,
                bo.currency,
                bo.source_account_id,
                bo.target_account_id,
                bo.created_at,
                bo.completed_at,
                source_customer.customer_code,
                target_customer.customer_code,
                audit.correlation_id,
                audit.actor_type,
                audit.details,
                actor.email

            ORDER BY bo.created_at DESC, bo.id DESC

            LIMIT :limit
            """
        ),
        {"limit": limit},
    )

    return _rows(rows)


@router.get("/operations/{operation_id}")
def control_tower_operation_trace(
    operation_id: UUID,
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Complete trace for one banking operation."""

    operation = _one_or_none(
        db.execute(
            text(
                """
                SELECT
                    id AS operation_id,
                    idempotency_key,
                    operation_type,
                    status,
                    source_account_id,
                    target_account_id,
                    amount,
                    currency,
                    created_at,
                    completed_at
                FROM public.banking_operations
                WHERE id = :operation_id
                """
            ),
            {"operation_id": operation_id},
        )
    )

    if operation is None:
        raise HTTPException(
            status_code=404,
            detail="Banking operation not found",
        )

    transactions = _rows(
        db.execute(
            text(
                """
                SELECT
                    tx.id AS transaction_id,
                    tx.account_id,
                    RIGHT(acc.account_number, 4)
                        AS account_last4,
                    tx.loan_id,
                    tx.transaction_type,
                    tx.direction,
                    tx.amount,
                    tx.currency,
                    tx.balance_after,
                    tx.description,
                    tx.created_at
                FROM public.transactions tx
                LEFT JOIN public.accounts acc
                    ON acc.id = tx.account_id
                WHERE tx.operation_id = :operation_id
                ORDER BY tx.created_at, tx.id
                """
            ),
            {"operation_id": operation_id},
        )
    )

    ledger = _rows(
        db.execute(
            text(
                """
                SELECT
                    id AS ledger_entry_id,
                    sequence_no,
                    account_id,
                    clearing_account_code,
                    direction,
                    amount,
                    currency,
                    created_at
                FROM public.ledger_entries
                WHERE operation_id = :operation_id
                ORDER BY sequence_no, id
                """
            ),
            {"operation_id": operation_id},
        )
    )

    audit = _rows(
        db.execute(
            text(
                """
                SELECT
                    ae.id AS audit_event_id,
                    ae.correlation_id,
                    ae.actor_type,
                    ae.action,
                    ae.entity_type,
                    ae.entity_id,
                    ae.result,
                    ae.details,
                    ae.occurred_at,
                    actor.email AS actor_email
                FROM public.audit_events ae

                LEFT JOIN public.app_users actor
                    ON actor.id::text = ae.details ->> 'actor_id'

                WHERE
                    ae.entity_id = :operation_id
                    OR ae.correlation_id = :operation_id

                ORDER BY ae.occurred_at, ae.id
                """
            ),
            {"operation_id": operation_id},
        )
    )

    lineage = _one_or_none(
        db.execute(
            text(
                """
                SELECT
                    fact.operation_key,
                    fact.source_operation_id,
                    fact.operation_type,
                    fact.status,
                    fact.amount,
                    fact.currency,
                    fact.transaction_count,
                    fact.debit_amount,
                    fact.credit_amount,
                    fact.last_run_id,

                    batch.batch_id,
                    batch.publication_status,
                    batch.is_current,
                    batch.gold_row_count,
                    batch.quality_gate_total,
                    batch.quality_gate_passed,
                    batch.rows_quarantined,
                    batch.published_at

                FROM dw.fact_banking_operations fact

                LEFT JOIN dataops.published_batches batch
                    ON batch.source_run_id = fact.last_run_id

                WHERE fact.source_operation_id = :operation_id

                ORDER BY
                    batch.is_current DESC NULLS LAST,
                    batch.published_at DESC NULLS LAST

                LIMIT 1
                """
            ),
            {"operation_id": operation_id},
        )
    )

    return {
        "operation": operation,
        "transactions": transactions,
        "ledger": ledger,
        "audit": audit,
        "lineage": lineage,
    }


@router.get("/decisions")
def control_tower_decisions(
    limit: int = Query(default=30, ge=1, le=100),
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Human administrative decisions with resolved reviewer identity."""

    rows = db.execute(
        text(
            """
            SELECT
                ae.id AS audit_event_id,
                ae.correlation_id,
                ae.action,
                ae.actor_type,
                ae.result,
                ae.entity_type,
                ae.entity_id,

                ae.details ->> 'decision'
                    AS decision,

                ae.details ->> 'reviewer_id'
                    AS reviewer_id,

                reviewer.email
                    AS reviewer_email,

                reviewer.role
                    AS reviewer_role,

                COALESCE(
                    onboarding_customer.full_name,
                    loan_customer.full_name
                ) AS subject_name,

                COALESCE(
                    onboarding_customer.customer_code,
                    loan_customer.customer_code
                ) AS subject_code,

                ae.details ->> 'evidence_reference_only'
                    AS evidence_ref,

                ae.details ->> 'reniec_result'
                    AS reniec_result,

                ae.details ->> 'loan_id'
                    AS loan_id,

                reviewed_loan.disbursement_status,
                reviewed_loan.scheduled_disbursement_at,
                reviewed_loan.disbursed_at,

                ae.details ->> 'tea_percent'
                    AS tea_percent,

                ae.details ->> 'human_decision'
                    AS human_decision,

                ae.details ->> 'llm_decision'
                    AS llm_decision,

                ae.occurred_at

            FROM public.audit_events ae

            LEFT JOIN public.app_users reviewer
                ON reviewer.id::text =
                   ae.details ->> 'reviewer_id'

            LEFT JOIN public.customers onboarding_customer
                ON ae.action = 'SYNTHETIC_ONBOARDING_REVIEW'
               AND onboarding_customer.id = ae.entity_id

            LEFT JOIN public.loan_applications loan_application
                ON ae.action = 'LOAN_APPLICATION_REVIEW'
               AND loan_application.id = ae.entity_id

            LEFT JOIN public.customers loan_customer
                ON loan_customer.id =
                   loan_application.customer_id

            LEFT JOIN public.loans reviewed_loan
                ON reviewed_loan.loan_application_id = loan_application.id

            WHERE ae.action IN (
                'SYNTHETIC_ONBOARDING_REVIEW',
                'LOAN_APPLICATION_REVIEW'
            )

            ORDER BY ae.occurred_at DESC, ae.id DESC

            LIMIT :limit
            """
        ),
        {"limit": limit},
    )

    return _rows(rows)


@router.get("/dataops")
def control_tower_dataops(
    limit: int = Query(default=10, ge=1, le=50),
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Recent DataOps runs, current Gold and quarantine summary."""

    runs = _rows(
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
                    gold_row_count,
                    error_message
                FROM analytics.vw_dataops_runs
                ORDER BY started_at DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    )

    current_gold = _one_or_none(
        db.execute(
            text(
                """
                SELECT *
                FROM analytics.vw_current_gold_status
                LIMIT 1
                """
            )
        )
    )

    quarantine = _rows(
        db.execute(
            text(
                """
                SELECT
                    run_id,
                    pipeline_name,
                    pipeline_status,
                    source_table,
                    rule_name,
                    reason,
                    rejected_records
                FROM analytics.vw_quarantine_summary
                ORDER BY
                    rejected_records DESC,
                    source_table,
                    rule_name
                LIMIT 50
                """
            )
        )
    )

    return {
        "runs": runs,
        "current_gold": current_gold,
        "quarantine": quarantine,
    }
    
@router.post("/actions/run-dataops")
def control_tower_run_dataops(
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Run the normal DataOps pipeline and publish a new valid Gold batch."""

    try:
        run_id = _run_bancocloud_pipeline(
            controlled_quality_test=False,
        )

        pipeline_run = _one_or_none(
            db.execute(
                text(
                    """
                    SELECT
                        run_id,
                        pipeline_name,
                        status,
                        started_at,
                        finished_at,
                        rows_extracted,
                        rows_accepted,
                        rows_quarantined
                    FROM dataops.pipeline_runs
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
        )

        if pipeline_run is None:
            raise HTTPException(
                status_code=500,
                detail="La ejecución DataOps no pudo ser localizada.",
            )

        if pipeline_run["status"] != "SUCCEEDED":
            return {
                "action": "RUN_DATAOPS",
                "run_id": run_id,
                "status": pipeline_run["status"],
                "published": False,
                "message": (
                    "La ejecución terminó sin cumplir las condiciones "
                    "necesarias para publicar una nueva versión Gold."
                ),
                "run": pipeline_run,
            }

        publication = _one_or_none(
            db.execute(
                text(
                    """
                    SELECT
                        batch_id,
                        source_run_id,
                        publication_state,
                        gold_row_count,
                        quality_total,
                        quality_passed
                    FROM dataops.publish_gold(:run_id)
                    """
                ),
                {"run_id": run_id},
            )
        )

        db.commit()

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
                    FROM dataops.current_published_batch
                    LIMIT 1
                    """
                )
            )
        )

        return {
            "action": "RUN_DATAOPS",
            "run_id": run_id,
            "status": pipeline_run["status"],
            "published": True,
            "message": (
                "Proceso de datos completado correctamente. "
                "La nueva versión Gold fue publicada."
            ),
            "run": pipeline_run,
            "publication": publication,
            "current_gold": current_gold,
            "executed_by": {
                "id": str(admin.id),
                "email": admin.email,
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "No fue posible completar y publicar "
                f"la ejecución DataOps: {exc}"
            ),
        ) from exc


@router.post("/actions/run-quality-test")
def control_tower_run_quality_test(
    admin: AppUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Execute the controlled quality scenario without replacing Gold."""

    current_gold_before = _one_or_none(
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
                FROM dataops.current_published_batch
                LIMIT 1
                """
            )
        )
    )

    try:
        run_id = _run_bancocloud_pipeline(
            controlled_quality_test=True,
        )

        pipeline_run = _one_or_none(
            db.execute(
                text(
                    """
                    SELECT
                        run_id,
                        pipeline_name,
                        status,
                        started_at,
                        finished_at,
                        rows_extracted,
                        rows_accepted,
                        rows_quarantined
                    FROM dataops.pipeline_runs
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
        )

        quality = _one_or_none(
            db.execute(
                text(
                    """
                    SELECT
                        COUNT(*)::INTEGER AS total,
                        COUNT(*) FILTER (
                            WHERE passed = TRUE
                        )::INTEGER AS passed,
                        COUNT(*) FILTER (
                            WHERE passed = FALSE
                        )::INTEGER AS failed
                    FROM dataops.quality_results
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
        )

        quarantine = _rows(
            db.execute(
                text(
                    """
                    SELECT
                        source_table,
                        rule_name,
                        reason,
                        COUNT(*)::INTEGER
                            AS rejected_records
                    FROM quarantine.rejected_records
                    WHERE run_id = :run_id
                    GROUP BY
                        source_table,
                        rule_name,
                        reason
                    ORDER BY
                        source_table,
                        rule_name,
                        reason
                    """
                ),
                {"run_id": run_id},
            )
        )

        current_gold_after = _one_or_none(
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
                    FROM dataops.current_published_batch
                    LIMIT 1
                    """
                )
            )
        )

        gold_protected = (
            current_gold_before is not None
            and current_gold_after is not None
            and current_gold_before["batch_id"]
            == current_gold_after["batch_id"]
        )

        return {
            "action": "RUN_QUALITY_TEST",
            "run_id": run_id,
            "status": (
                pipeline_run["status"]
                if pipeline_run
                else "UNKNOWN"
            ),
            "published": False,
            "gold_protected": gold_protected,
            "message": (
                "Prueba controlada completada. "
                "El registro inválido fue aislado y "
                "la versión Gold vigente no fue reemplazada."
            ),
            "run": pipeline_run,
            "quality": quality,
            "quarantine": quarantine,
            "gold_before": current_gold_before,
            "gold_after": current_gold_after,
            "executed_by": {
                "id": str(admin.id),
                "email": admin.email,
            },
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "No fue posible completar la prueba "
                f"controlada de calidad: {exc}"
            ),
        ) from exc
        
        