from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.session import SessionLocal  # noqa: E402


VALID_TERMS = {6, 12, 18, 24, 36, 48, 60}
VALID_CURRENCIES = {"PEN", "USD"}


def _serialize(value: Any) -> Any:
    if isinstance(value, (UUID, Decimal, datetime, date)):
        return str(value)
    return value


def _json_payload(row: dict[str, Any]) -> str:
    return json.dumps(
        {key: _serialize(value) for key, value in row.items()},
        ensure_ascii=False,
        sort_keys=True,
    )


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def validate_customer(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "customer_code", "full_name", "email", "region", "onboarding_status", "created_at"):
        if not _nonempty(row.get(field)):
            errors.append(f"{field}: requerido")
    if row.get("onboarding_status") not in {"PENDING", "VERIFIED", "REJECTED"}:
        errors.append("onboarding_status: valor no permitido")
    return errors


def validate_account(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("customer_id") not in ctx["customers"]:
        errors.append("customer_id: cliente inexistente")
    if row.get("account_type") not in {"SAVINGS", "CHECKING"}:
        errors.append("account_type: valor no permitido")
    if str(row.get("currency", "")).strip() not in VALID_CURRENCIES:
        errors.append("currency: moneda no permitida")
    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    balance = Decimal(str(row.get("balance", "0")))
    if balance < Decimal("0"):
        errors.append("balance: no puede ser negativo")
    return errors


def validate_transaction(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("account_id") not in ctx["accounts"]:
        errors.append("account_id: cuenta inexistente")
    if row.get("operation_id") not in ctx["operations"]:
        errors.append("operation_id: operación inexistente")
    if str(row.get("currency", "")).strip() not in VALID_CURRENCIES:
        errors.append("currency: moneda no permitida")
    if row.get("direction") not in {"CREDIT", "DEBIT"}:
        errors.append("direction: valor no permitido")
    transaction_type = row.get("transaction_type")
    if transaction_type not in {
        "DEPOSIT",
        "WITHDRAWAL",
        "CARD_PAYMENT",
        "TRANSFER_IN",
        "TRANSFER_OUT",
        "LOAN_DISBURSEMENT",
        "REVERSAL",
    }:
        errors.append("transaction_type: valor no permitido")
    if transaction_type == "LOAN_DISBURSEMENT" and not _nonempty(row.get("loan_id")):
        errors.append("loan_id: requerido para desembolso de préstamo")
    amount = Decimal(str(row.get("amount", "0")))
    if amount <= Decimal("0"):
        errors.append("amount: debe ser positivo")
    balance_after = Decimal(str(row.get("balance_after", "0")))
    if balance_after < Decimal("0"):
        errors.append("balance_after: no puede ser negativo")
    return errors


def validate_operation(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if str(row.get("currency", "")).strip() not in VALID_CURRENCIES:
        errors.append("currency: moneda no permitida")
    operation_type = row.get("operation_type")
    if not _nonempty(operation_type):
        errors.append("operation_type: requerido")
    if operation_type == "LOAN_DISBURSEMENT":
        if row.get("source_account_id") is not None:
            errors.append("source_account_id: debe ser nulo para desembolso de préstamo")
        if row.get("target_account_id") not in ctx["accounts"]:
            errors.append("target_account_id: cuenta destino inexistente")

    if operation_type == "TRANSFER":
        if row.get("source_account_id") not in ctx["accounts"]:
            errors.append("source_account_id: cuenta origen inexistente")
        if row.get("target_account_id") not in ctx["accounts"]:
            errors.append("target_account_id: cuenta destino inexistente")
        if row.get("source_account_id") == row.get("target_account_id"):
            errors.append("target_account_id: debe diferir de la cuenta origen")

    if operation_type == "INTERBANK_TRANSFER":
        if row.get("source_account_id") not in ctx["accounts"]:
            errors.append("source_account_id: cuenta origen inexistente")
        if row.get("target_account_id") is not None:
            errors.append("target_account_id: debe ser nulo para transferencia interbancaria")

    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    amount = Decimal(str(row.get("amount", "0")))
    if amount <= Decimal("0"):
        errors.append("amount: debe ser positivo")
    return errors


def validate_loan_application(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("customer_id") not in ctx["customers"]:
        errors.append("customer_id: cliente inexistente")
    amount = Decimal(str(row.get("requested_amount", "0")))
    if amount < Decimal("500.00") or amount > Decimal("50000.00"):
        errors.append("requested_amount: fuera del rango permitido")
    if str(row.get("currency", "")).strip() not in VALID_CURRENCIES:
        errors.append("currency: moneda no permitida")
    if row.get("term_months") not in VALID_TERMS:
        errors.append("term_months: plazo no permitido")
    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    return errors


def validate_loan(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("customer_id") not in ctx["customers"]:
        errors.append("customer_id: cliente inexistente")
    principal = Decimal(str(row.get("principal", "0")))
    annual_rate = Decimal(str(row.get("annual_rate", "0")))
    if principal <= Decimal("0"):
        errors.append("principal: debe ser positivo")
    if annual_rate <= Decimal("0") or annual_rate > Decimal("100"):
        errors.append("annual_rate: fuera del rango permitido")
    if row.get("term_months") not in VALID_TERMS:
        errors.append("term_months: plazo no permitido")
    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    return errors


def validate_installment(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("loan_id") not in ctx["loans"]:
        errors.append("loan_id: préstamo inexistente")
    due = Decimal(str(row.get("due_amount", "0")))
    paid = Decimal(str(row.get("paid_amount", "0")))
    if int(row.get("installment_number", 0)) <= 0:
        errors.append("installment_number: debe ser positivo")
    if due <= Decimal("0"):
        errors.append("due_amount: debe ser positivo")
    if paid < Decimal("0") or paid > due:
        errors.append("paid_amount: fuera de rango")
    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    return errors


def validate_payment(row: dict[str, Any], ctx: dict[str, set[Any]]) -> list[str]:
    errors: list[str] = []
    if row.get("installment_id") not in ctx["installments"]:
        errors.append("installment_id: cuota inexistente")
    if row.get("operation_id") not in ctx["operations"]:
        errors.append("operation_id: operación inexistente")
    amount = Decimal(str(row.get("amount", "0")))
    if amount <= Decimal("0"):
        errors.append("amount: debe ser positivo")
    if not _nonempty(row.get("status")):
        errors.append("status: requerido")
    return errors


DATASETS: list[dict[str, Any]] = [
    {
        "name": "customers",
        "source_columns": ["id", "customer_code", "full_name", "email", "region", "onboarding_status", "created_at"],
        "stage_columns": ["customer_id", "customer_code", "region", "onboarding_status", "created_at"],
        "validator": validate_customer,
        "transform": lambda r: {
            "customer_id": r["id"],
            "customer_code": r["customer_code"],
            "region": r["region"],
            "onboarding_status": r["onboarding_status"],
            "created_at": r["created_at"],
        },
    },
    {
        "name": "accounts",
        "source_columns": ["id", "customer_id", "account_number", "account_type", "currency", "balance", "status", "created_at"],
        "stage_columns": ["account_id", "customer_id", "account_last4", "account_type", "currency", "balance", "status", "created_at"],
        "validator": validate_account,
        "transform": lambda r: {
            "account_id": r["id"],
            "customer_id": r["customer_id"],
            "account_last4": str(r["account_number"])[-8:],
            "account_type": r["account_type"],
            "currency": str(r["currency"]).strip(),
            "balance": r["balance"],
            "status": r["status"],
            "created_at": r["created_at"],
        },
    },
    {
        "name": "banking_operations",
        "source_columns": ["id", "idempotency_key", "request_hash", "operation_type", "status", "source_account_id", "target_account_id", "amount", "currency", "created_at", "completed_at"],
        "stage_columns": ["operation_id", "operation_type", "status", "source_account_id", "target_account_id", "amount", "currency", "created_at", "completed_at"],
        "validator": validate_operation,
        "transform": lambda r: {
            "operation_id": r["id"],
            "operation_type": r["operation_type"],
            "status": r["status"],
            "source_account_id": r["source_account_id"],
            "target_account_id": r["target_account_id"],
            "amount": r["amount"],
            "currency": str(r["currency"]).strip(),
            "created_at": r["created_at"],
            "completed_at": r["completed_at"],
        },
    },
    {
        "name": "transactions",
        "source_columns": ["id", "account_id", "card_id", "loan_id", "operation_id", "idempotency_key", "transaction_type", "direction", "amount", "currency", "balance_after", "description", "created_at"],
        "stage_columns": ["transaction_id", "account_id", "loan_id", "operation_id", "transaction_type", "direction", "amount", "currency", "balance_after", "created_at"],
        "validator": validate_transaction,
        "transform": lambda r: {
            "transaction_id": r["id"],
            "account_id": r["account_id"],
            "loan_id": r["loan_id"],
            "operation_id": r["operation_id"],
            "transaction_type": r["transaction_type"],
            "direction": r["direction"],
            "amount": r["amount"],
            "currency": str(r["currency"]).strip(),
            "balance_after": r["balance_after"],
            "created_at": r["created_at"],
        },
    },
    {
        "name": "loan_applications",
        "source_columns": ["id", "customer_id", "requested_amount", "currency", "term_months", "purpose", "status", "human_review_required", "requested_at", "reviewed_at"],
        "stage_columns": ["application_id", "customer_id", "requested_amount", "currency", "term_months", "purpose", "status", "human_review_required", "requested_at", "reviewed_at"],
        "validator": validate_loan_application,
        "transform": lambda r: {
            "application_id": r["id"],
            "customer_id": r["customer_id"],
            "requested_amount": r["requested_amount"],
            "currency": str(r["currency"]).strip(),
            "term_months": r["term_months"],
            "purpose": r["purpose"],
            "status": r["status"],
            "human_review_required": r["human_review_required"],
            "requested_at": r["requested_at"],
            "reviewed_at": r["reviewed_at"],
        },
    },
    {
        "name": "loans",
        "source_columns": ["id", "customer_id", "principal", "annual_rate", "term_months", "status", "requested_at", "loan_application_id"],
        "stage_columns": ["loan_id", "customer_id", "principal", "annual_rate", "term_months", "status", "requested_at", "loan_application_id"],
        "validator": validate_loan,
        "transform": lambda r: {
            "loan_id": r["id"],
            "customer_id": r["customer_id"],
            "principal": r["principal"],
            "annual_rate": r["annual_rate"],
            "term_months": r["term_months"],
            "status": r["status"],
            "requested_at": r["requested_at"],
            "loan_application_id": r["loan_application_id"],
        },
    },
    {
        "name": "loan_installments",
        "source_columns": ["id", "loan_id", "installment_number", "due_date", "due_amount", "paid_amount", "status"],
        "stage_columns": ["installment_id", "loan_id", "installment_number", "due_date", "due_amount", "paid_amount", "status"],
        "validator": validate_installment,
        "transform": lambda r: {
            "installment_id": r["id"],
            "loan_id": r["loan_id"],
            "installment_number": r["installment_number"],
            "due_date": r["due_date"],
            "due_amount": r["due_amount"],
            "paid_amount": r["paid_amount"],
            "status": r["status"],
        },
    },
    {
        "name": "loan_payments",
        "source_columns": ["id", "installment_id", "operation_id", "amount", "status", "paid_at"],
        "stage_columns": ["payment_id", "installment_id", "operation_id", "amount", "status", "paid_at"],
        "validator": validate_payment,
        "transform": lambda r: {
            "payment_id": r["id"],
            "installment_id": r["installment_id"],
            "operation_id": r["operation_id"],
            "amount": r["amount"],
            "status": r["status"],
            "paid_at": r["paid_at"],
        },
    },
]


def _inject_controlled_quality_fixture(
    dataset_name: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Agrega un único dato deliberadamente inválido para validar Data Quality.

    El fixture existe solamente en memoria durante una ejecución de prueba.
    No modifica las tablas operacionales del schema public.
    """

    if dataset_name != "banking_operations":
        return rows

    if not rows:
        raise RuntimeError(
            "Controlled quality fixture requires at least one banking operation"
        )

    synthetic = dict(rows[0])

    synthetic_id = uuid4()

    synthetic["id"] = synthetic_id
    synthetic["idempotency_key"] = f"dq-{synthetic_id.hex[:20]}"
    synthetic["request_hash"] = "f" * 64

    # EUR es deliberadamente inválido:
    # BancoCloud únicamente admite PEN y USD.
    synthetic["currency"] = "EUR"

    return [*rows, synthetic]


def _insert_row(db: Any, table_name: str, run_id: UUID, values: dict[str, Any]) -> None:
    columns = ["run_id", *values.keys()]
    placeholders = [":run_id", *[f":{name}" for name in values]]
    sql = text(
        f"INSERT INTO {table_name} ({', '.join(columns)}) "
        f"VALUES ({', '.join(placeholders)})"
    )
    db.execute(sql, {"run_id": run_id, **values})


def _record_quality(
    db: Any,
    *,
    run_id: UUID,
    dataset_name: str,
    rule_name: str,
    passed: bool,
    rows_checked: int,
    rows_failed: int,
    details: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO dataops.quality_results (
                run_id, dataset_name, rule_name, severity, passed,
                rows_checked, rows_failed, details
            )
            VALUES (
                :run_id, :dataset_name, :rule_name, 'ERROR', :passed,
                :rows_checked, :rows_failed, :details
            )
            """
        ),
        {
            "run_id": run_id,
            "dataset_name": dataset_name,
            "rule_name": rule_name,
            "passed": passed,
            "rows_checked": rows_checked,
            "rows_failed": rows_failed,
            "details": details,
        },
    )


def run_pipeline(*, controlled_quality_test: bool = False) -> UUID:
    run_id = uuid4()

    pipeline_name = (
        "bancocloud_operational_to_staging_negative_test"
        if controlled_quality_test
        else "bancocloud_operational_to_staging"
    )

    with SessionLocal.begin() as db:
        db.execute(
            text(
                """
                INSERT INTO dataops.pipeline_runs (
                    run_id, pipeline_name, status, source_system
                )
                VALUES (
                    :run_id, :pipeline_name, 'RUNNING', 'BancoCloud PostgreSQL'
                )
                """
            ),
            {"run_id": run_id, "pipeline_name": pipeline_name},
        )

    extracted_total = 0
    accepted_total = 0
    quarantined_total = 0

    try:
        with SessionLocal.begin() as db:
            context: dict[str, set[Any]] = {
                "customers": set(db.execute(text("SELECT id FROM public.customers")).scalars()),
                "accounts": set(db.execute(text("SELECT id FROM public.accounts")).scalars()),
                "operations": set(db.execute(text("SELECT id FROM public.banking_operations")).scalars()),
                "loans": set(db.execute(text("SELECT id FROM public.loans")).scalars()),
                "installments": set(db.execute(text("SELECT id FROM public.loan_installments")).scalars()),
            }

            for dataset in DATASETS:
                name = dataset["name"]
                source_columns: list[str] = dataset["source_columns"]
                stage_columns: list[str] = dataset["stage_columns"]
                validator: Callable[[dict[str, Any], dict[str, set[Any]]], list[str]] = dataset["validator"]
                transform: Callable[[dict[str, Any]], dict[str, Any]] = dataset["transform"]

                rows = [
                    dict(row)
                    for row in db.execute(
                        text(
                            f"SELECT {', '.join(source_columns)} "
                            f"FROM public.{name} ORDER BY 1"
                        )
                    ).mappings()
                ]

                if controlled_quality_test:
                    rows = _inject_controlled_quality_fixture(
                        name,
                        rows,
                    )

                extracted_total += len(rows)
                failed = 0

                for row in rows:
                    raw_values = {column: row[column] for column in source_columns}
                    _insert_row(db, f"raw.{name}", run_id, raw_values)

                    errors = validator(row, context)

                    if errors:
                        failed += 1
                        quarantined_total += 1
                        db.execute(
                            text(
                                """
                                INSERT INTO quarantine.rejected_records (
                                    run_id, source_table, source_record_id,
                                    rule_name, reason, payload
                                )
                                VALUES (
                                    :run_id, :source_table, :source_record_id,
                                    'record_validation', :reason, CAST(:payload AS jsonb)
                                )
                                """
                            ),
                            {
                                "run_id": run_id,
                                "source_table": name,
                                "source_record_id": str(row.get("id", "")),
                                "reason": "; ".join(errors),
                                "payload": _json_payload(row),
                            },
                        )
                        continue

                    stage_values = transform(row)
                    if list(stage_values.keys()) != stage_columns:
                        raise RuntimeError(
                            f"Transform contract mismatch for {name}: "
                            f"{list(stage_values.keys())} != {stage_columns}"
                        )
                    _insert_row(db, f"staging.{name}", run_id, stage_values)
                    accepted_total += 1

                raw_count = db.execute(
                    text(f"SELECT COUNT(*) FROM raw.{name} WHERE run_id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one()

                _record_quality(
                    db,
                    run_id=run_id,
                    dataset_name=name,
                    rule_name="source_to_raw_reconciliation",
                    passed=(raw_count == len(rows)),
                    rows_checked=len(rows),
                    rows_failed=0 if raw_count == len(rows) else abs(raw_count - len(rows)),
                    details=f"source={len(rows)} raw={raw_count}",
                )

                _record_quality(
                    db,
                    run_id=run_id,
                    dataset_name=name,
                    rule_name="record_validation",
                    passed=(failed == 0),
                    rows_checked=len(rows),
                    rows_failed=failed,
                    details=f"accepted={len(rows) - failed} quarantined={failed}",
                )

            status = "SUCCEEDED" if quarantined_total == 0 else "QUALITY_GATE_FAILED"

            db.execute(
                text(
                    """
                    UPDATE dataops.pipeline_runs
                    SET status = :status,
                        finished_at = NOW(),
                        rows_extracted = :rows_extracted,
                        rows_accepted = :rows_accepted,
                        rows_quarantined = :rows_quarantined
                    WHERE run_id = :run_id
                    """
                ),
                {
                    "status": status,
                    "rows_extracted": extracted_total,
                    "rows_accepted": accepted_total,
                    "rows_quarantined": quarantined_total,
                    "run_id": run_id,
                },
            )

        print("=" * 68)
        print("BancoCloud DataOps - Operational -> RAW -> STAGING")
        print("=" * 68)
        print(f"run_id            : {run_id}")
        print(f"status            : {'SUCCEEDED' if quarantined_total == 0 else 'QUALITY_GATE_FAILED'}")
        print(f"rows_extracted    : {extracted_total}")
        print(f"rows_accepted     : {accepted_total}")
        print(f"rows_quarantined  : {quarantined_total}")
        print("=" * 68)
        return run_id

    except Exception as exc:
        with SessionLocal.begin() as db:
            db.execute(
                text(
                    """
                    UPDATE dataops.pipeline_runs
                    SET status = 'FAILED',
                        finished_at = NOW(),
                        error_message = :error_message
                    WHERE run_id = :run_id
                    """
                ),
                {
                    "run_id": run_id,
                    "error_message": str(exc)[:4000],
                },
            )
        raise


if __name__ == "__main__":
    run_pipeline()
