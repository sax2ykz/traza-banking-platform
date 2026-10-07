from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from prefect import flow, get_run_logger, task
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.session import SessionLocal  # noqa: E402
from dataops.pipeline_core import run_pipeline  # noqa: E402


@task(
    name="01 - Verificar conectividad PostgreSQL",
    retries=2,
    retry_delay_seconds=5,
)
def check_database() -> dict[str, Any]:
    logger = get_run_logger()
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    NOW() AS checked_at
                """
            )
        ).mappings().one()

    payload = {
        "database_name": result["database_name"],
        "database_user": result["database_user"],
        "checked_at": result["checked_at"].isoformat(),
    }
    logger.info(
        "PostgreSQL disponible: database=%s user=%s",
        payload["database_name"],
        payload["database_user"],
    )
    return payload


@task(
    name="02 - Ejecutar pipeline Operational-RAW-STAGING",
    retries=1,
    retry_delay_seconds=5,
)
def execute_pipeline() -> str:
    logger = get_run_logger()
    run_id = run_pipeline()
    logger.info("Pipeline DataOps ejecutado. run_id=%s", run_id)
    return str(run_id)


@task(name="03 - Validar estado de pipeline")
def validate_pipeline_run(run_id: str) -> dict[str, Any]:
    logger = get_run_logger()
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    run_id,
                    pipeline_name,
                    status,
                    rows_extracted,
                    rows_accepted,
                    rows_quarantined,
                    started_at,
                    finished_at,
                    error_message
                FROM dataops.pipeline_runs
                WHERE run_id = CAST(:run_id AS uuid)
                """
            ),
            {"run_id": run_id},
        ).mappings().one()

    payload = {
        "run_id": str(row["run_id"]),
        "pipeline_name": row["pipeline_name"],
        "status": row["status"],
        "rows_extracted": int(row["rows_extracted"] or 0),
        "rows_accepted": int(row["rows_accepted"] or 0),
        "rows_quarantined": int(row["rows_quarantined"] or 0),
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
        "error_message": row["error_message"],
    }

    if payload["status"] != "SUCCEEDED":
        raise RuntimeError(
            f"El pipeline no terminó en SUCCEEDED. "
            f"status={payload['status']} error={payload['error_message']}"
        )
    if payload["rows_extracted"] != payload["rows_accepted"]:
        raise RuntimeError(
            "Reconciliación inválida: "
            f"extracted={payload['rows_extracted']} "
            f"accepted={payload['rows_accepted']}"
        )

    logger.info(
        "Pipeline validado: %s extraídos, %s aceptados, %s cuarentena.",
        payload["rows_extracted"],
        payload["rows_accepted"],
        payload["rows_quarantined"],
    )
    return payload


@task(name="04 - Verificar Quality Gates")
def validate_quality_gates(run_id: str) -> dict[str, Any]:
    logger = get_run_logger()
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    dataset_name,
                    rule_name,
                    passed,
                    rows_checked,
                    rows_failed,
                    details
                FROM dataops.quality_results
                WHERE run_id = CAST(:run_id AS uuid)
                ORDER BY dataset_name, rule_name
                """
            ),
            {"run_id": run_id},
        ).mappings().all()

    if not rows:
        raise RuntimeError("No se encontraron Quality Gates para el run_id.")

    failed = [
        {
            "dataset_name": row["dataset_name"],
            "rule_name": row["rule_name"],
            "rows_failed": int(row["rows_failed"] or 0),
            "details": row["details"],
        }
        for row in rows
        if not row["passed"]
    ]
    if failed:
        raise RuntimeError(f"Quality Gates fallidos: {failed}")

    payload = {
        "quality_gate_count": len(rows),
        "passed": len(rows),
        "failed": 0,
    }
    logger.info(
        "Quality Gates OK: %s/%s aprobados.",
        payload["passed"],
        payload["quality_gate_count"],
    )
    return payload


@task(name="05 - Verificar cuarentena")
def validate_quarantine(run_id: str) -> dict[str, int]:
    logger = get_run_logger()
    with SessionLocal() as db:
        count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM quarantine.rejected_records
                WHERE run_id = CAST(:run_id AS uuid)
                """
            ),
            {"run_id": run_id},
        ).scalar_one()

    count = int(count)
    if count != 0:
        raise RuntimeError(
            f"La ejecución contiene {count} registro(s) en cuarentena."
        )

    logger.info("Quarantine limpia: 0 registros rechazados.")
    return {"quarantined_records": count}


@task(name="06 - Generar resumen de ejecución")
def build_summary(
    database_info: dict[str, Any],
    pipeline_info: dict[str, Any],
    quality_info: dict[str, Any],
    quarantine_info: dict[str, int],
) -> dict[str, Any]:
    logger = get_run_logger()
    summary = {
        "database": database_info["database_name"],
        "run_id": pipeline_info["run_id"],
        "pipeline_status": pipeline_info["status"],
        "rows_extracted": pipeline_info["rows_extracted"],
        "rows_accepted": pipeline_info["rows_accepted"],
        "rows_quarantined": pipeline_info["rows_quarantined"],
        "quality_gates_passed": quality_info["passed"],
        "quality_gates_total": quality_info["quality_gate_count"],
        "quarantine_records": quarantine_info["quarantined_records"],
    }
    logger.info(
        "Resumen BancoCloud DataOps: status=%s | rows=%s/%s | quality=%s/%s | quarantine=%s",
        summary["pipeline_status"],
        summary["rows_accepted"],
        summary["rows_extracted"],
        summary["quality_gates_passed"],
        summary["quality_gates_total"],
        summary["quarantine_records"],
    )
    return summary


@flow(
    name="BancoCloud DataOps - Operational to Staging",
    retries=0,
    log_prints=True,
)
def bancocloud_dataops_flow() -> dict[str, Any]:
    database_info = check_database()
    run_id = execute_pipeline()
    pipeline_info = validate_pipeline_run(run_id)
    quality_info = validate_quality_gates(run_id)
    quarantine_info = validate_quarantine(run_id)
    return build_summary(
        database_info,
        pipeline_info,
        quality_info,
        quarantine_info,
    )


if __name__ == "__main__":
    result = bancocloud_dataops_flow()
    print("\n" + "=" * 72)
    print("BancoCloud DataOps - Prefect summary")
    print("=" * 72)
    for key, value in result.items():
        print(f"{key:24}: {value}")
    print("=" * 72)
