"""LOCAL-ONLY synthetic API + PostgreSQL integration demo. Intentionally leaves the synthetic data for DataOps.

Requires live Uvicorn, local PostgreSQL Docker, and app/router changes from Paso 2.9.
Does NOT perform real KYC or use authentic financial/customer data.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import AuditEvent, Customer  # noqa: E402
from app.session import SessionLocal  # noqa: E402

API = 'http://127.0.0.1:8000'


def require(response: httpx.Response, expected: int, title: str):
    if response.status_code != expected:
        raise AssertionError(f'{title}: expected HTTP {expected}, received {response.status_code}: {response.text[:300]}')
    print(f'[OK] {title}: HTTP {expected}')
    return response.json()


def new_customer_and_account(client: httpx.Client, currency: str):
    marker = uuid4().hex[:12].upper()
    customer = require(client.post('/api/v1/customers', json={
        'customer_code': f'BC-{marker}', 'full_name': 'Usuario Sintetico',
        'email': f'bc-{marker.lower()}@example.invalid', 'region': 'Lima',
    }), 201, f'Cliente sintetico {currency}')
    customer_id = UUID(customer['id'])
    # Local-only human-review simulation (not KYC); no admin endpoint exists.
    with SessionLocal.begin() as db:
        entity = db.get(Customer, customer_id, with_for_update=True)
        assert entity is not None and entity.onboarding_status == 'PENDING'
        entity.onboarding_status = 'VERIFIED'
        db.add(AuditEvent(
            correlation_id=uuid4(), actor_type='STAFF', action='DEV_SYNTHETIC_ONBOARDING_REVIEW',
            entity_type='CUSTOMER', entity_id=customer_id, result='SUCCESS',
            details={'synthetic': True, 'real_kyc_performed': False, 'environment': 'local-dev'},
        ))
    account = require(client.post('/api/v1/accounts', json={
        'customer_id': str(customer_id), 'account_type': 'SAVINGS', 'currency': currency,
    }), 201, f'Cuenta sintetica {currency}')
    assert Decimal(str(account['balance'])) == 0
    return account['id']


def key():
    return 'BC9-' + uuid4().hex[:24]


def amount(v):
    return Decimal(str(v))


def do_withdraw(account_id: str, amount_s: str, request_key: str):
    with httpx.Client(base_url=API, timeout=20) as client:
        return client.post('/api/v1/operations/withdraw', json={
            'account_id': account_id, 'amount': amount_s,
            'currency': 'PEN', 'idempotency_key': request_key,
        })


def journal_balance(db, account_id):
    return amount(db.execute(text('''SELECT COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE -amount END),0)
                              FROM ledger_entries WHERE account_id = :id'''), {'id': UUID(account_id)}).scalar_one())


def main():
    if sys.argv[1:] != ['--solo-local-sintetico']:
        sys.exit('Usage: python scripts/demo_operations.py --solo-local-sintetico')
    with httpx.Client(base_url=API, timeout=15) as client:
        require(client.get('/health/db'), 200, 'API y PostgreSQL conectados')
        source = new_customer_and_account(client, 'PEN')
        target = new_customer_and_account(client, 'PEN')
        usd = new_customer_and_account(client, 'USD')
        deposit_key = key()
        deposit = {'account_id': source, 'amount': '100.00', 'currency': 'PEN', 'idempotency_key': deposit_key}
        funded = require(client.post('/api/v1/operations/deposit', json=deposit), 201, 'Deposito sintetico S/100')
        assert funded['replayed'] is False and amount(funded['balances_after'][source]) == 100
        replay = require(client.post('/api/v1/operations/deposit', json=deposit), 200, 'Replay idempotente del deposito')
        assert replay['replayed'] is True and replay['operation_id'] == funded['operation_id']
        require(client.post('/api/v1/operations/deposit', json=dict(deposit, amount='101.00')), 409,
                'Rechazo de reutilizacion de clave con contenido diferente')
        moved = require(client.post('/api/v1/operations/transfer', json={
            'source_account_id': source, 'target_account_id': target,
            'amount': '30.00', 'currency': 'PEN', 'idempotency_key': key(),
        }), 201, 'Transferencia sintetica S/30')
        assert amount(moved['balances_after'][source]) == 70 and amount(moved['balances_after'][target]) == 30
        withdrawn = require(do_withdraw(source, '20.00', key()), 201, 'Retiro sintetico S/20')
        assert amount(withdrawn['balances_after'][source]) == 50
        require(do_withdraw(source, '9999.00', key()), 409, 'Rechazo de fondos insuficientes')
        require(client.post('/api/v1/operations/transfer', json={
            'source_account_id': source, 'target_account_id': usd,
            'amount': '2.00', 'currency': 'PEN', 'idempotency_key': key(),
        }), 409, 'Rechazo de cuentas con distintas monedas')
        require(client.post('/api/v1/operations/deposit', json=dict(deposit, amount='-1', idempotency_key=key())),
                422, 'Rechazo de monto negativo')
        # Two different requests race for the same S/50. Only ONE S/40 withdrawal can commit.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(do_withdraw, source, '40.00', key()) for _ in range(2)]
            responses = [f.result() for f in futures]
        codes = sorted(r.status_code for r in responses)
        assert codes == [201, 409], f'Unexpected concurrency result: {codes}; {[r.text[:150] for r in responses]}'
        print('[OK] Concurrencia: un retiro de S/40 aprobado y otro rechazado: no hay sobregiro')
        one = require(client.get(f'/api/v1/accounts/{source}'), 200, 'Saldo final de origen')
        two = require(client.get(f'/api/v1/accounts/{target}'), 200, 'Saldo final de destino')
        assert amount(one['balance']) == 10 and amount(two['balance']) == 30
        print('[OK] Saldos finales: origen S/10.00; destino S/30.00')
        src_mov = require(client.get(f'/api/v1/accounts/{source}/movements'), 200, 'Consulta de movimientos de origen')
        dst_mov = require(client.get(f'/api/v1/accounts/{target}/movements'), 200, 'Consulta de movimientos de destino')
        assert len(src_mov) == 4 and len(dst_mov) == 1, (src_mov, dst_mov)
        print('[OK] Movimientos: cuatro en origen, uno en destino')
    with SessionLocal() as db:
        for aid, expected in [(source, Decimal('10.00')), (target, Decimal('30.00'))]:
            journal = journal_balance(db, aid)
            assert journal == expected, f'Ledger imbalance for {aid}: {journal} != {expected}'
        print('[OK] Reconciliacion: saldos coinciden con asientos contables')
        check = db.execute(text('''SELECT op.id FROM banking_operations op
          JOIN ledger_entries l ON l.operation_id=op.id
          WHERE op.id = ANY(:ids) GROUP BY op.id
          HAVING SUM(CASE WHEN l.direction='DEBIT' THEN l.amount ELSE -l.amount END) != 0
             OR COUNT(l.id) != 2'''), {
            'ids': [UUID(funded['operation_id']), UUID(moved['operation_id']), UUID(withdrawn['operation_id'])]
        }).all()
        assert not check, f'Unbalanced operations: {check}'
        print('[OK] Asientos de operaciones iniciales: DEBIT = CREDIT')
    print('\nRESULTADO: PASO 2.9 - DEMOSTRACION LOCAL TRANSACCIONAL COMPLETADA')
    print('NOTA: seguridad de acceso no implementada. NO publicar estos endpoints en Internet.')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, RuntimeError, httpx.HTTPError) as error:
        print(f'[ERROR] {error}', file=sys.stderr)
        sys.exit(1)
