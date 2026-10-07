"""Scheduled, idempotent loan disbursement for BancoCloud.

Approval and disbursement are deliberately separate events:

    APPROVED -> SCHEDULED -> COMPLETED

The scheduler is safe to retry. A deterministic idempotency key and row-level
locking prevent the same loan from crediting the customer twice.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AuditEvent,
    BankingOperation,
    Loan,
    LoanApplication,
    LoanInstallment,
    LedgerEntry,
    Transaction,
)
from app.services.financial_rules import assert_balanced, request_fingerprint
from app.services.loan_rules import add_months

DEFAULT_TIMEZONE = "America/Lima"
DEFAULT_HOUR_LOCAL = 9
DEFAULT_DELAY_BUSINESS_DAYS = 1
DEFAULT_POLL_SECONDS = 60


@dataclass(frozen=True)
class DisbursementRunResult:
    scheduled: int = 0
    processed: int = 0
    replayed: int = 0
    failed: int = 0


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def auto_process_enabled() -> bool:
    return _bool_env("LOAN_DISBURSEMENT_AUTO_PROCESS", False)


def schedule_existing_enabled() -> bool:
    return _bool_env("LOAN_SCHEDULE_EXISTING_APPROVED", False)


def poll_seconds() -> int:
    raw = os.getenv("LOAN_DISBURSEMENT_POLL_SECONDS", str(DEFAULT_POLL_SECONDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_POLL_SECONDS
    return max(30, min(value, 3600))


def disbursement_timezone() -> ZoneInfo:
    name = os.getenv("LOAN_DISBURSEMENT_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def disbursement_delay_business_days() -> int:
    raw = os.getenv(
        "LOAN_DISBURSEMENT_DELAY_BUSINESS_DAYS",
        str(DEFAULT_DELAY_BUSINESS_DAYS),
    )
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_DELAY_BUSINESS_DAYS
    return max(0, min(value, 10))


def disbursement_hour_local() -> int:
    raw = os.getenv("LOAN_DISBURSEMENT_HOUR_LOCAL", str(DEFAULT_HOUR_LOCAL))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_HOUR_LOCAL
    return max(0, min(value, 23))


def next_business_disbursement_at(
    approved_at: datetime,
    *,
    delay_business_days: int | None = None,
    tz: ZoneInfo | None = None,
    hour_local: int | None = None,
) -> datetime:
    """Return the scheduled UTC timestamp for a future business-day disbursement.

    BancoCloud's business-day policy counts Monday-Friday only; official holidays are
    intentionally not modeled. This is a configurable operational rule, not a claim of
    a universal banking SLA.
    """

    if approved_at.tzinfo is None:
        approved_at = approved_at.replace(tzinfo=timezone.utc)

    tz = tz or disbursement_timezone()
    delay = (
        disbursement_delay_business_days()
        if delay_business_days is None
        else max(0, int(delay_business_days))
    )
    hour = disbursement_hour_local() if hour_local is None else max(0, min(int(hour_local), 23))

    local_approved = approved_at.astimezone(tz)
    candidate = local_approved.date()

    remaining = delay
    while remaining > 0:
        candidate += timedelta(days=1)
        if candidate.weekday() < 5:
            remaining -= 1

    # If delay is zero but today's configured processing time has passed,
    # schedule immediately rather than producing a timestamp in the past.
    local_scheduled = datetime.combine(candidate, time(hour=hour), tzinfo=tz)
    if delay == 0 and local_scheduled < local_approved:
        local_scheduled = local_approved

    return local_scheduled.astimezone(timezone.utc)


def _find_active_account(
    db: Session,
    *,
    customer_id: UUID,
    currency: str,
    preferred_account_id: UUID | None,
    lock: bool = False,
) -> Account | None:
    stmt = select(Account).where(
        Account.customer_id == customer_id,
        Account.currency == currency,
        Account.status == "ACTIVE",
    )

    if preferred_account_id is not None:
        preferred_stmt = stmt.where(Account.id == preferred_account_id)
        if lock:
            preferred_stmt = preferred_stmt.with_for_update()
        account = db.scalar(preferred_stmt)
        if account is not None:
            return account
        return None

    stmt = stmt.order_by(Account.created_at, Account.id).limit(1)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _reviewer_id_for_application(db: Session, application_id: UUID) -> UUID | None:
    raw = db.execute(
        text(
            """
            SELECT NULLIF(details ->> 'reviewer_id', '')
            FROM public.audit_events
            WHERE action = 'LOAN_APPLICATION_REVIEW'
              AND entity_type = 'LOAN_APPLICATION'
              AND entity_id = :application_id
              AND details ->> 'decision' = 'APPROVED'
            ORDER BY occurred_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"application_id": application_id},
    ).scalar_one_or_none()

    if not raw:
        return None

    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def schedule_existing_approved_loans(now: datetime | None = None) -> int:
    """Schedule legacy APPROVED loans only when the explicit backfill flag is on.

    The guard avoids unexpectedly crediting old local/demo loans after an upgrade.
    """

    if not schedule_existing_enabled():
        return 0

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    scheduled = 0

    from app.session import SessionLocal

    with SessionLocal.begin() as db:
        loans = db.scalars(
            select(Loan)
            .where(
                Loan.status == "APPROVED",
                Loan.disbursement_status == "PENDING",
                Loan.scheduled_disbursement_at.is_(None),
            )
            .order_by(Loan.requested_at, Loan.id)
            .with_for_update(skip_locked=True)
        ).all()

        for loan in loans:
            application = (
                db.get(LoanApplication, loan.loan_application_id)
                if loan.loan_application_id is not None
                else None
            )
            if application is None:
                continue

            account = _find_active_account(
                db,
                customer_id=loan.customer_id,
                currency=application.currency,
                preferred_account_id=(
                    loan.disbursement_account_id
                    or application.disbursement_account_id
                ),
            )
            if account is None:
                continue

            # Legacy scheduling starts from "now" when the original approval is
            # already in the past, preventing immediate catch-up on old datasets.
            approval_reference = application.reviewed_at or loan.approved_at or now
            if approval_reference.tzinfo is None:
                approval_reference = approval_reference.replace(tzinfo=timezone.utc)
            scheduling_reference = max(approval_reference, now)

            loan.approved_at = loan.approved_at or application.reviewed_at or now
            loan.approved_by_user_id = loan.approved_by_user_id or _reviewer_id_for_application(
                db, application.id
            )
            loan.disbursement_account_id = account.id
            application.disbursement_account_id = application.disbursement_account_id or account.id
            loan.scheduled_disbursement_at = next_business_disbursement_at(scheduling_reference)
            loan.disbursement_status = "SCHEDULED"

            db.add(
                AuditEvent(
                    correlation_id=uuid4(),
                    actor_type="SYSTEM",
                    action="LOAN_DISBURSEMENT_SCHEDULED",
                    entity_type="LOAN",
                    entity_id=loan.id,
                    result="SUCCESS",
                    details={
                        "loan_id": str(loan.id),
                        "disbursement_account_id": str(account.id),
                        "account_last4": account.account_number[-4:],
                        "scheduled_disbursement_at": loan.scheduled_disbursement_at.isoformat(),
                        "legacy_upgrade": True,
                    },
                )
            )
            scheduled += 1

    return scheduled


def _process_one_due_loan(loan_id: UUID, now: datetime) -> tuple[str, UUID | None]:
    from app.session import SessionLocal

    with SessionLocal.begin() as db:
        loan = db.scalar(select(Loan).where(Loan.id == loan_id).with_for_update())
        if loan is None:
            return "SKIPPED", None

        if loan.disbursement_status == "COMPLETED":
            return "REPLAYED", loan.disbursement_operation_id

        if (
            loan.status != "APPROVED"
            or loan.disbursement_status != "SCHEDULED"
            or loan.scheduled_disbursement_at is None
            or loan.scheduled_disbursement_at > now
        ):
            return "SKIPPED", None

        application = (
            db.get(LoanApplication, loan.loan_application_id)
            if loan.loan_application_id is not None
            else None
        )
        if application is None:
            loan.disbursement_status = "FAILED"
            return "FAILED", None

        account = _find_active_account(
            db,
            customer_id=loan.customer_id,
            currency=application.currency,
            preferred_account_id=loan.disbursement_account_id,
            lock=True,
        )
        if account is None:
            loan.disbursement_status = "FAILED"
            db.add(
                AuditEvent(
                    correlation_id=uuid4(),
                    actor_type="SYSTEM",
                    action="LOAN_DISBURSEMENT_FAILED",
                    entity_type="LOAN",
                    entity_id=loan.id,
                    result="FAILED",
                    details={
                        "loan_id": str(loan.id),
                        "reason": "Cuenta de desembolso no disponible, inactiva o incompatible.",
                    },
                )
            )
            return "FAILED", None

        amount = Decimal(str(loan.principal)).quantize(Decimal("0.01"))
        currency = application.currency
        idempotency_key = f"LOAN-DISBURSEMENT-{loan.id}"

        # Same transaction-scoped advisory lock pattern used by normal banking
        # operations. It serializes retries from scheduler/startup overlap.
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": idempotency_key},
        )

        digest = request_fingerprint(
            kind="LOAN_DISBURSEMENT",
            accounts=[str(loan.id), str(account.id)],
            amount=amount,
            currency=currency,
        )

        existing = db.scalar(
            select(BankingOperation).where(
                BankingOperation.idempotency_key == idempotency_key
            )
        )
        if existing is not None:
            if existing.request_hash != digest:
                loan.disbursement_status = "FAILED"
                db.add(
                    AuditEvent(
                        correlation_id=existing.id,
                        actor_type="SYSTEM",
                        action="LOAN_DISBURSEMENT_FAILED",
                        entity_type="LOAN",
                        entity_id=loan.id,
                        result="FAILED",
                        details={
                            "loan_id": str(loan.id),
                            "reason": "Conflicto de idempotencia del desembolso.",
                        },
                    )
                )
                return "FAILED", existing.id

            if existing.status == "COMPLETED":
                loan.disbursement_status = "COMPLETED"
                loan.disbursement_operation_id = existing.id
                loan.disbursed_at = loan.disbursed_at or existing.completed_at or now
                loan.status = "ACTIVE"
                return "REPLAYED", existing.id

            # A previous partial attempt should have rolled back atomically. A
            # persisted non-completed operation is therefore treated as unsafe.
            loan.disbursement_status = "FAILED"
            return "FAILED", existing.id

        operation_id = uuid4()
        operation = BankingOperation(
            id=operation_id,
            idempotency_key=idempotency_key,
            request_hash=digest,
            operation_type="LOAN_DISBURSEMENT",
            status="PENDING",
            source_account_id=None,
            target_account_id=account.id,
            amount=amount,
            currency=currency,
        )
        db.add(operation)
        db.flush()

        account.balance += amount

        journal = [
            ("DEBIT", amount, currency),
            ("CREDIT", amount, currency),
        ]
        assert_balanced(journal, currency)

        db.add_all(
            [
                LedgerEntry(
                    operation_id=operation_id,
                    sequence_no=1,
                    clearing_account_code="LOAN_RECEIVABLE",
                    direction="DEBIT",
                    amount=amount,
                    currency=currency,
                ),
                LedgerEntry(
                    operation_id=operation_id,
                    sequence_no=2,
                    account_id=account.id,
                    direction="CREDIT",
                    amount=amount,
                    currency=currency,
                ),
            ]
        )

        db.add(
            Transaction(
                id=uuid4(),
                account_id=account.id,
                loan_id=loan.id,
                operation_id=operation_id,
                idempotency_key=f"{operation_id}:0",
                transaction_type="LOAN_DISBURSEMENT",
                direction="CREDIT",
                amount=amount,
                currency=currency,
                balance_after=account.balance,
                description="Desembolso de préstamo",
            )
        )

        # Due dates follow the actual disbursement date, not only approval.
        local_date = now.astimezone(disbursement_timezone()).date()
        installments = db.scalars(
            select(LoanInstallment)
            .where(LoanInstallment.loan_id == loan.id)
            .order_by(LoanInstallment.installment_number)
            .with_for_update()
        ).all()
        for installment in installments:
            installment.due_date = add_months(
                local_date,
                installment.installment_number,
            )

        operation.status = "COMPLETED"
        operation.completed_at = now

        loan.disbursement_status = "COMPLETED"
        loan.disbursement_operation_id = operation_id
        loan.disbursed_at = now
        loan.status = "ACTIVE"

        db.add_all(
            [
                AuditEvent(
                    correlation_id=operation_id,
                    actor_type="SYSTEM",
                    action="FINANCIAL_OPERATION",
                    entity_type="BANKING_OPERATION",
                    entity_id=operation_id,
                    result="SUCCESS",
                    details={
                        "kind": "LOAN_DISBURSEMENT",
                        "channel": "DIGITAL_BANKING",
                        "mode": "SCHEDULED_DISBURSEMENT",
                        "loan_id": str(loan.id),
                        "customer_id": str(loan.customer_id),
                        "account_id": str(account.id),
                    },
                ),
                AuditEvent(
                    correlation_id=operation_id,
                    actor_type="SYSTEM",
                    action="LOAN_DISBURSEMENT_COMPLETED",
                    entity_type="LOAN",
                    entity_id=loan.id,
                    result="SUCCESS",
                    details={
                        "loan_id": str(loan.id),
                        "operation_id": str(operation_id),
                        "amount": format(amount, ".2f"),
                        "currency": currency,
                        "account_last4": account.account_number[-4:],
                        "balance_after": format(account.balance, ".2f"),
                    },
                ),
            ]
        )

        return "PROCESSED", operation_id


def process_due_loan_disbursements(now: datetime | None = None) -> DisbursementRunResult:
    """Process all due scheduled disbursements; safe to call repeatedly."""

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    scheduled = schedule_existing_approved_loans(now)

    from app.session import SessionLocal

    with SessionLocal() as db:
        loan_ids = list(
            db.scalars(
                select(Loan.id)
                .where(
                    Loan.status == "APPROVED",
                    Loan.disbursement_status == "SCHEDULED",
                    Loan.scheduled_disbursement_at.is_not(None),
                    Loan.scheduled_disbursement_at <= now,
                )
                .order_by(Loan.scheduled_disbursement_at, Loan.id)
            ).all()
        )

    processed = 0
    replayed = 0
    failed = 0

    for loan_id in loan_ids:
        result, _ = _process_one_due_loan(loan_id, now)
        if result == "PROCESSED":
            processed += 1
        elif result == "REPLAYED":
            replayed += 1
        elif result == "FAILED":
            failed += 1

    return DisbursementRunResult(
        scheduled=scheduled,
        processed=processed,
        replayed=replayed,
        failed=failed,
    )
