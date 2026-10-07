"""Authenticated BancoCloud financial operations with ownership, idempotency and audit controls.

Each operation is one PostgreSQL transaction, guarded with a transaction-scoped
advisory lock per idempotency key and row locks on affected accounts. A real
bank needs authenticated principal/account ownership and mature accounting.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, BankingOperation, Customer, LedgerEntry, Transaction
from app.services.financial_rules import assert_balanced, money, request_fingerprint
from app.services.transaction_schemas import (
    InterbankTransferRequest,
    MovementResult,
    OneAccountRequest,
    OperationResult,
    ThirdPartyBeneficiaryRequest,
    ThirdPartyBeneficiaryResult,
    ThirdPartyTransferRequest,
    TransferRequest,
)
from app.session import SessionLocal
from app.security import current_user, verify_customer_access
from app.security_models import AppUser

router = APIRouter(prefix='/api/v1', tags=['Synthetic banking operations'])


INTERBANK_BANKS = {
    "BCP": "BCP",
    "INTERBANK": "Interbank",
    "BBVA": "BBVA",
    "SCOTIABANK": "Scotiabank",
    "BANBIF": "BanBif",
    "BANCO_NACION": "Banco de la Nación",
}


def normalized_account_number(value: str) -> str:
    return value.strip().upper()


def masked_holder_name(full_name: str) -> str:
    parts = [part for part in full_name.strip().split() if part]

    if not parts:
        return "Titular BancoCloud"

    if len(parts) == 1:
        return parts[0]

    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."

    return f"{parts[0]} {parts[1]} {parts[2][0]}."


def masked_external_account(cci: str) -> str:
    return f"••••{cci[-4:]}"


def ensure_customer_user(user: AppUser) -> None:
    if user.role != "CUSTOMER" or user.customer_id is None:
        raise HTTPException(
            status_code=403,
            detail="Only customers may execute financial operations",
        )


def local_only(request: Request) -> None:
    # Local development remains restricted to loopback.
    # Azure demo is public but remains protected by JWT, roles and ownership checks.
    app_env = os.getenv("APP_ENV", "local").strip().lower()

    if app_env == "azure":
        return

    if (
        request.client is None
        or request.client.host not in {"127.0.0.1", "::1", "testclient"}
    ):
        raise HTTPException(
            status_code=403,
            detail="Development-only endpoint",
        )


def lock_idempotency(db: Session, key: str) -> None:
    # Transaction-scoped lock: parallel requests with the same key serialize.
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': key})


def fetch_existing(db: Session, key: str, expected_hash: str, user: AppUser) -> OperationResult | None:
    op = db.scalar(select(BankingOperation).where(BankingOperation.idempotency_key == key))
    if op is None:
        return None
    if op.request_hash != expected_hash:
        raise HTTPException(409, 'Idempotency key was previously used with different parameters')
    if op.status != 'COMPLETED':
        raise HTTPException(409, 'Operation is not completed')
    transactions = db.scalars(select(Transaction).join(Account, Account.id == Transaction.account_id)
                              .where(Transaction.operation_id == op.id, Account.customer_id == user.customer_id)).all()
    if not transactions:
        raise HTTPException(500, 'Completed operation missing movements')
    return OperationResult(
        operation_id=op.id, status=op.status, operation_type=op.operation_type,
        amount=op.amount, currency=op.currency,
        balances_after={str(m.account_id): m.balance_after for m in transactions}, replayed=True,
    )


def lock_accounts(db: Session, ids: list[UUID], currency: str) -> dict[UUID, Account]:
    locked = {}
    # Deterministic order prevents account-lock inversion between opposing transfers.
    for account_id in sorted(set(ids), key=str):
        account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
        if account is None:
            raise HTTPException(404, 'Account not found')
        if account.status != 'ACTIVE':
            raise HTTPException(409, 'Account is not active')
        if account.currency != currency:
            raise HTTPException(409, 'Account currency mismatch')
        locked[account_id] = account
    return locked


def execute(kind: Literal['DEPOSIT', 'WITHDRAWAL', 'TRANSFER'], payload: OneAccountRequest | TransferRequest, user: AppUser) -> tuple[OperationResult, int]:
    amount = money(payload.amount)
    if kind == 'TRANSFER':
        assert isinstance(payload, TransferRequest)
        src, dst = payload.source_account_id, payload.target_account_id
        if src == dst:
            raise HTTPException(422, 'Source and target must differ')
        ids = [src, dst]
    else:
        assert isinstance(payload, OneAccountRequest)
        src = dst = payload.account_id
        ids = [payload.account_id]
    if user.role != 'CUSTOMER' or user.customer_id is None:
        raise HTTPException(403, 'Only the owning customer may execute financial operations')
    digest = request_fingerprint(kind=kind, accounts=[str(user.id)] + [str(x) for x in ids], amount=amount, currency=payload.currency)
    with SessionLocal.begin() as db:
        lock_idempotency(db, payload.idempotency_key)
        # Ownership checked before replaying any idempotency-key result.
        accounts = lock_accounts(db, ids, payload.currency)
        owner_account = accounts[src] if kind != 'DEPOSIT' else accounts[dst]
        verify_customer_access(user, owner_account.customer_id, allow_admin=False)

        if kind == 'TRANSFER' and accounts[dst].customer_id != user.customer_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    'Para transferir a otro cliente BancoCloud usa '
                    'la modalidad A terceros BancoCloud.'
                ),
            )

        old = fetch_existing(db, payload.idempotency_key, digest, user)
        if old is not None:
            return old, 200
        if kind != 'DEPOSIT' and accounts[src].balance < amount:
            raise HTTPException(409, 'Insufficient funds')
        op_id = uuid4()
        now = datetime.now(timezone.utc)
        operation = BankingOperation(
            id=op_id, idempotency_key=payload.idempotency_key, request_hash=digest,
            operation_type=kind, status='PENDING',
            source_account_id=src if kind != 'DEPOSIT' else None,
            target_account_id=dst if kind != 'WITHDRAWAL' else None,
            amount=amount, currency=payload.currency,
        )
        db.add(operation)
        db.flush()
        if kind == 'DEPOSIT':
            accounts[dst].balance += amount
            journal = [('DEBIT', amount, payload.currency), ('CREDIT', amount, payload.currency)]
            ledger = [
                LedgerEntry(operation_id=op_id, sequence_no=1, clearing_account_code='CASH_CLEARING', direction='DEBIT', amount=amount, currency=payload.currency),
                LedgerEntry(operation_id=op_id, sequence_no=2, account_id=dst, direction='CREDIT', amount=amount, currency=payload.currency),
            ]
            movement_specs = [(dst, 'DEPOSIT', 'CREDIT', f'{op_id}:0')]
        elif kind == 'WITHDRAWAL':
            accounts[src].balance -= amount
            journal = [('DEBIT', amount, payload.currency), ('CREDIT', amount, payload.currency)]
            ledger = [
                LedgerEntry(operation_id=op_id, sequence_no=1, account_id=src, direction='DEBIT', amount=amount, currency=payload.currency),
                LedgerEntry(operation_id=op_id, sequence_no=2, clearing_account_code='CASH_CLEARING', direction='CREDIT', amount=amount, currency=payload.currency),
            ]
            movement_specs = [(src, 'WITHDRAWAL', 'DEBIT', f'{op_id}:0')]
        else:
            accounts[src].balance -= amount
            accounts[dst].balance += amount
            journal = [('DEBIT', amount, payload.currency), ('CREDIT', amount, payload.currency)]
            ledger = [
                LedgerEntry(operation_id=op_id, sequence_no=1, account_id=src, direction='DEBIT', amount=amount, currency=payload.currency),
                LedgerEntry(operation_id=op_id, sequence_no=2, account_id=dst, direction='CREDIT', amount=amount, currency=payload.currency),
            ]
            movement_specs = [
                (src, 'TRANSFER_OUT', 'DEBIT', f'{op_id}:0'),
                (dst, 'TRANSFER_IN', 'CREDIT', f'{op_id}:1'),
            ]
        assert_balanced(journal, payload.currency)
        db.add_all(ledger)
        for aid, tx_type, direction, movement_key in movement_specs:
            db.add(Transaction(
                id=uuid4(), account_id=aid, operation_id=op_id, idempotency_key=movement_key,
                transaction_type=tx_type, direction=direction, amount=amount,
                currency=payload.currency, balance_after=accounts[aid].balance,
                description='Operación financiera BancoCloud',
            ))
        operation.status = 'COMPLETED'
        operation.completed_at = now
        db.add(AuditEvent(
            correlation_id=op_id, actor_type='SYSTEM', action='FINANCIAL_OPERATION',
            entity_type='BANKING_OPERATION', entity_id=op_id, result='SUCCESS',
            details={
                'kind': kind,
                'channel': 'DIGITAL_BANKING',
                'mode': 'AUTHENTICATED_BANKING',
                'actor_id': str(user.id),
                'transfer_scope': (
                    'OWN_ACCOUNTS'
                    if kind == 'TRANSFER'
                    else None
                ),
            },
        ))
        # Transaction commits when exiting SessionLocal.begin(). Failure rolls back
        # operation, journal, movements and BOTH account balances together.
        result = OperationResult(
            operation_id=op_id, status='COMPLETED', operation_type=kind,
            amount=amount, currency=payload.currency,
            balances_after={str(aid): accounts[aid].balance for aid in ids
                            if accounts[aid].customer_id == user.customer_id}, replayed=False,
        )
    return result, 201


def resolve_third_party_target(
    db: Session,
    *,
    source_account_id: UUID,
    target_account_number: str,
    user: AppUser,
) -> tuple[Account, Account, Customer]:
    ensure_customer_user(user)

    source = db.get(Account, source_account_id)

    if source is None:
        raise HTTPException(status_code=404, detail="Cuenta origen no encontrada.")

    verify_customer_access(
        user,
        source.customer_id,
        allow_admin=False,
    )

    if source.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="La cuenta origen no está activa.")

    normalized = normalized_account_number(target_account_number)

    target = db.scalar(
        select(Account).where(Account.account_number == normalized)
    )

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="La cuenta BancoCloud indicada no existe.",
        )

    if target.status != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail="La cuenta destino no está activa.",
        )

    if target.id == source.id:
        raise HTTPException(
            status_code=422,
            detail="La cuenta destino debe ser distinta de la cuenta origen.",
        )

    if target.customer_id == user.customer_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "La cuenta indicada también te pertenece. "
                "Usa la modalidad Entre mis cuentas."
            ),
        )

    if target.currency != source.currency:
        raise HTTPException(
            status_code=409,
            detail="La cuenta destino debe usar la misma moneda que la cuenta origen.",
        )

    customer = db.get(Customer, target.customer_id)

    if customer is None:
        raise HTTPException(
            status_code=409,
            detail="No fue posible validar al titular de la cuenta destino.",
        )

    return source, target, customer


def execute_third_party_transfer(
    payload: ThirdPartyTransferRequest,
    user: AppUser,
) -> tuple[OperationResult, int]:
    ensure_customer_user(user)
    amount = money(payload.amount)
    target_number = normalized_account_number(payload.target_account_number)

    with SessionLocal.begin() as db:
        lock_idempotency(db, payload.idempotency_key)

        target_id = db.scalar(
            select(Account.id).where(Account.account_number == target_number)
        )

        if target_id is None:
            raise HTTPException(
                status_code=404,
                detail="La cuenta BancoCloud indicada no existe.",
            )

        accounts = lock_accounts(
            db,
            [payload.source_account_id, target_id],
            payload.currency,
        )

        source = accounts[payload.source_account_id]
        target = accounts[target_id]

        verify_customer_access(
            user,
            source.customer_id,
            allow_admin=False,
        )

        if target.account_number != target_number:
            raise HTTPException(
                status_code=409,
                detail="La cuenta destino cambió durante la validación.",
            )

        if target.customer_id == user.customer_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    "La cuenta indicada también te pertenece. "
                    "Usa la modalidad Entre mis cuentas."
                ),
            )

        digest = request_fingerprint(
            kind="TRANSFER_THIRD_PARTY",
            accounts=[
                str(user.id),
                str(source.id),
                target.account_number,
            ],
            amount=amount,
            currency=payload.currency,
        )

        old = fetch_existing(
            db,
            payload.idempotency_key,
            digest,
            user,
        )

        if old is not None:
            return old, 200

        if source.balance < amount:
            raise HTTPException(status_code=409, detail="Saldo insuficiente.")

        op_id = uuid4()
        now = datetime.now(timezone.utc)

        operation = BankingOperation(
            id=op_id,
            idempotency_key=payload.idempotency_key,
            request_hash=digest,
            operation_type="TRANSFER",
            status="PENDING",
            source_account_id=source.id,
            target_account_id=target.id,
            amount=amount,
            currency=payload.currency,
        )

        db.add(operation)
        db.flush()

        source.balance -= amount
        target.balance += amount

        journal = [
            ("DEBIT", amount, payload.currency),
            ("CREDIT", amount, payload.currency),
        ]

        assert_balanced(journal, payload.currency)

        db.add_all(
            [
                LedgerEntry(
                    operation_id=op_id,
                    sequence_no=1,
                    account_id=source.id,
                    direction="DEBIT",
                    amount=amount,
                    currency=payload.currency,
                ),
                LedgerEntry(
                    operation_id=op_id,
                    sequence_no=2,
                    account_id=target.id,
                    direction="CREDIT",
                    amount=amount,
                    currency=payload.currency,
                ),
                Transaction(
                    id=uuid4(),
                    account_id=source.id,
                    operation_id=op_id,
                    idempotency_key=f"{op_id}:0",
                    transaction_type="TRANSFER_OUT",
                    direction="DEBIT",
                    amount=amount,
                    currency=payload.currency,
                    balance_after=source.balance,
                    description="Transferencia a tercero BancoCloud",
                ),
                Transaction(
                    id=uuid4(),
                    account_id=target.id,
                    operation_id=op_id,
                    idempotency_key=f"{op_id}:1",
                    transaction_type="TRANSFER_IN",
                    direction="CREDIT",
                    amount=amount,
                    currency=payload.currency,
                    balance_after=target.balance,
                    description="Transferencia recibida de tercero BancoCloud",
                ),
            ]
        )

        operation.status = "COMPLETED"
        operation.completed_at = now

        db.add(
            AuditEvent(
                correlation_id=op_id,
                actor_type="SYSTEM",
                action="FINANCIAL_OPERATION",
                entity_type="BANKING_OPERATION",
                entity_id=op_id,
                result="SUCCESS",
                details={
                    "kind": "TRANSFER",
                    "channel": "DIGITAL_BANKING",
                    "mode": "AUTHENTICATED_BANKING",
                    "actor_id": str(user.id),
                    "transfer_scope": "BANCOCLOUD_THIRD_PARTY",
                    "target_account_last4": target.account_number[-4:],
                    "target_customer_id": str(target.customer_id),
                },
            )
        )

        result = OperationResult(
            operation_id=op_id,
            status="COMPLETED",
            operation_type="TRANSFER",
            amount=amount,
            currency=payload.currency,
            balances_after={str(source.id): source.balance},
            replayed=False,
        )

    return result, 201


def execute_interbank_transfer(
    payload: InterbankTransferRequest,
    user: AppUser,
) -> tuple[OperationResult, int]:
    ensure_customer_user(user)
    amount = money(payload.amount)

    with SessionLocal.begin() as db:
        lock_idempotency(db, payload.idempotency_key)

        accounts = lock_accounts(
            db,
            [payload.source_account_id],
            payload.currency,
        )

        source = accounts[payload.source_account_id]

        verify_customer_access(
            user,
            source.customer_id,
            allow_admin=False,
        )

        bank_name = INTERBANK_BANKS[payload.destination_bank]

        digest = request_fingerprint(
            kind="INTERBANK_TRANSFER",
            accounts=[
                str(user.id),
                str(source.id),
                payload.destination_bank,
                payload.cci,
            ],
            amount=amount,
            currency=payload.currency,
        )

        old = fetch_existing(
            db,
            payload.idempotency_key,
            digest,
            user,
        )

        if old is not None:
            return old, 200

        if source.balance < amount:
            raise HTTPException(status_code=409, detail="Saldo insuficiente.")

        op_id = uuid4()
        now = datetime.now(timezone.utc)

        operation = BankingOperation(
            id=op_id,
            idempotency_key=payload.idempotency_key,
            request_hash=digest,
            operation_type="INTERBANK_TRANSFER",
            status="PENDING",
            source_account_id=source.id,
            target_account_id=None,
            amount=amount,
            currency=payload.currency,
        )

        db.add(operation)
        db.flush()

        source.balance -= amount

        journal = [
            ("DEBIT", amount, payload.currency),
            ("CREDIT", amount, payload.currency),
        ]

        assert_balanced(journal, payload.currency)

        db.add_all(
            [
                LedgerEntry(
                    operation_id=op_id,
                    sequence_no=1,
                    account_id=source.id,
                    direction="DEBIT",
                    amount=amount,
                    currency=payload.currency,
                ),
                LedgerEntry(
                    operation_id=op_id,
                    sequence_no=2,
                    clearing_account_code="INTERBANK_CLEARING",
                    direction="CREDIT",
                    amount=amount,
                    currency=payload.currency,
                ),
                Transaction(
                    id=uuid4(),
                    account_id=source.id,
                    operation_id=op_id,
                    idempotency_key=f"{op_id}:0",
                    transaction_type="TRANSFER_OUT",
                    direction="DEBIT",
                    amount=amount,
                    currency=payload.currency,
                    balance_after=source.balance,
                    description=(
                        f"Transferencia a {bank_name} · "
                        f"CCI {masked_external_account(payload.cci)}"
                    ),
                ),
            ]
        )

        operation.status = "COMPLETED"
        operation.completed_at = now

        db.add(
            AuditEvent(
                correlation_id=op_id,
                actor_type="SYSTEM",
                action="FINANCIAL_OPERATION",
                entity_type="BANKING_OPERATION",
                entity_id=op_id,
                result="SUCCESS",
                details={
                    "kind": "INTERBANK_TRANSFER",
                    "channel": "DIGITAL_BANKING",
                    "mode": "INTERBANK_TRANSFER",
                    "actor_id": str(user.id),
                    "transfer_scope": "INTERBANK",
                    "destination_bank_code": payload.destination_bank,
                    "destination_bank_name": bank_name,
                    "external_account_masked": masked_external_account(payload.cci),
                },
            )
        )

        result = OperationResult(
            operation_id=op_id,
            status="COMPLETED",
            operation_type="INTERBANK_TRANSFER",
            amount=amount,
            currency=payload.currency,
            balances_after={str(source.id): source.balance},
            replayed=False,
        )

    return result, 201


from fastapi.responses import JSONResponse


def outcome(result: OperationResult, code: int) -> JSONResponse:
    return JSONResponse(status_code=code, content=result.model_dump(mode='json'))


@router.post('/operations/deposit', response_model=OperationResult)
def deposit(payload: OneAccountRequest, request: Request, user: AppUser = Depends(current_user)):
    local_only(request)
    return outcome(*execute('DEPOSIT', payload, user))


@router.post('/operations/withdraw', response_model=OperationResult)
def withdraw(payload: OneAccountRequest, request: Request, user: AppUser = Depends(current_user)):
    local_only(request)
    return outcome(*execute('WITHDRAWAL', payload, user))


@router.post('/operations/transfer', response_model=OperationResult)
def transfer(payload: TransferRequest, request: Request, user: AppUser = Depends(current_user)):
    local_only(request)
    return outcome(*execute('TRANSFER', payload, user))


@router.post(
    '/operations/transfer/beneficiary/resolve',
    response_model=ThirdPartyBeneficiaryResult,
)
def resolve_bancocloud_beneficiary(
    payload: ThirdPartyBeneficiaryRequest,
    request: Request,
    user: AppUser = Depends(current_user),
):
    local_only(request)

    with SessionLocal() as db:
        _, target, customer = resolve_third_party_target(
            db,
            source_account_id=payload.source_account_id,
            target_account_number=payload.target_account_number,
            user=user,
        )

        return ThirdPartyBeneficiaryResult(
            holder_display=masked_holder_name(customer.full_name),
            account_last4=target.account_number[-4:],
            account_type=target.account_type,
            currency=target.currency,
        )


@router.post(
    '/operations/transfer/third-party',
    response_model=OperationResult,
)
def transfer_third_party(
    payload: ThirdPartyTransferRequest,
    request: Request,
    user: AppUser = Depends(current_user),
):
    local_only(request)
    return outcome(*execute_third_party_transfer(payload, user))


@router.post(
    '/operations/transfer/interbank',
    response_model=OperationResult,
)
def transfer_interbank(
    payload: InterbankTransferRequest,
    request: Request,
    user: AppUser = Depends(current_user),
):
    local_only(request)
    return outcome(*execute_interbank_transfer(payload, user))


@router.get('/accounts/{account_id}/movements', response_model=list[MovementResult])
def movements(account_id: UUID, request: Request, limit: int = 30, user: AppUser = Depends(current_user)):
    local_only(request)
    if limit < 1 or limit > 100:
        raise HTTPException(422, 'Limit must be between 1 and 100')
    with SessionLocal() as db:
        account = db.get(Account, account_id)
        if account is None:
            raise HTTPException(404, 'Account not found')
        verify_customer_access(user, account.customer_id)
        return db.scalars(select(Transaction).where(Transaction.account_id == account_id)
                          .order_by(Transaction.created_at.desc(), Transaction.id.desc()).limit(limit)).all()
