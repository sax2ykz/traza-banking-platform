"""One-shot LOCAL integration demo for synthetic cards and loan applications.

Requires Uvicorn on 127.0.0.1:8000, live PostgreSQL, and --solo-local-sintetico.
Creates entirely synthetic data. It never validates real identity or grants a loan.
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import Account, AuditEvent, Card, Customer, Loan, LoanApplication  # noqa: E402
from app.session import SessionLocal  # noqa: E402

BASE_URL = 'http://127.0.0.1:8000'


def check(response, expected: int, title: str):
    assert response.status_code == expected, (
        f'{title}: esperaba HTTP {expected}, recibi {response.status_code}: {response.text[:220]}'
    )
    print(f'[OK] {title}: HTTP {expected}')
    return response.json()


def main():
    if sys.argv[1:] != ['--solo-local-sintetico']:
        sys.exit('Uso: python scripts/demo_cards_loans.py --solo-local-sintetico')
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        check(client.get('/health/db'), 200, 'FastAPI y PostgreSQL operativos')
        suffix = uuid4().hex[:12].upper()
        customer = check(client.post('/api/v1/customers', json={
            'customer_code': f'BC-{suffix}',
            'full_name': 'Cliente Simulado Dos',
            'email': f'bc-sim-{suffix.lower()}@example.invalid',
            'region': 'Lima',
        }), 201, 'Cliente creado con estado PENDING')
        customer_id = UUID(customer['id'])
        assert customer['onboarding_status'] == 'PENDING'
        req = {
            'customer_id': str(customer_id), 'requested_amount': '2500.00',
            'currency': 'PEN', 'term_months': 12,
            'purpose': 'Compra simulada de equipo',
        }
        check(client.post('/api/v1/loan-applications', json=req), 409,
              'Solicitud de prestamo bloqueada antes de onboarding')
        # Simulate local human KYC, consistent with previous demos. No external provider used.
        with SessionLocal.begin() as db:
            entity = db.get(Customer, customer_id, with_for_update=True)
            assert entity and entity.onboarding_status == 'PENDING'
            entity.onboarding_status = 'VERIFIED'
            db.add(AuditEvent(
                correlation_id=uuid4(), actor_type='STAFF',
                action='DEV_SYNTHETIC_ONBOARDING_REVIEW', entity_type='CUSTOMER',
                entity_id=entity.id, result='SUCCESS',
                details={'synthetic': True, 'real_kyc_performed': False},
            ))
        print('[OK] Revision humana de onboarding SIMULADA solo en local')
        account = check(client.post('/api/v1/accounts', json={
            'customer_id': str(customer_id), 'account_type': 'SAVINGS', 'currency': 'PEN',
        }), 201, 'Cuenta sintetica creada')
        account_id = UUID(account['id'])
        card = check(client.post('/api/v1/cards', json={'account_id': str(account_id)}),
                     201, 'Referencia de tarjeta sintetica emitida')
        assert card['account_id'] == str(account_id)
        assert card['card_reference'].startswith('BC-SIM-') and len(card['last_four']) == 4
        check(client.get(f"/api/v1/cards/{card['id']}"), 200, 'Consulta de tarjeta simulada')
        cards = check(client.get(f'/api/v1/accounts/{account_id}/cards'),
                      200, 'Listado de tarjetas de la cuenta')
        assert any(entry['id'] == card['id'] for entry in cards)
        check(client.post('/api/v1/cards', json={'account_id': str(uuid4())}), 404,
              'Cuenta inexistente no permite emitir tarjeta')
        with SessionLocal.begin() as db:
            acct = db.get(Account, account_id, with_for_update=True)
            assert acct
            acct.status = 'FROZEN'
        check(client.post('/api/v1/cards', json={'account_id': str(account_id)}),
              409, 'Cuenta congelada no permite emitir tarjeta')
        with SessionLocal.begin() as db:
            acct = db.get(Account, account_id, with_for_update=True)
            assert acct
            acct.status = 'ACTIVE'
        print('[OK] Estado de la cuenta restaurado a ACTIVE')

        with SessionLocal() as db:
            original_loans = len(db.scalars(select(Loan).where(Loan.customer_id == customer_id)).all())
        application = check(client.post('/api/v1/loan-applications', json=req),
                            201, 'Solicitud de prestamo sintetica recibida')
        assert application['status'] == 'PENDING' and application['human_review_required'] is True
        assert application['reviewed_at'] is None
        queried = check(client.get(f"/api/v1/loan-applications/{application['id']}"),
                        200, 'Consulta de la solicitud')
        assert queried['status'] == 'PENDING'
        listed = check(client.get(f'/api/v1/customers/{customer_id}/loan-applications'),
                       200, 'Listado de solicitudes del cliente')
        assert any(a['id'] == application['id'] for a in listed)
        check(client.post('/api/v1/loan-applications', json=dict(req, requested_amount='0')),
              422, 'Monto cero rechazado')
        check(client.post('/api/v1/loan-applications', json=dict(req, requested_amount='1500.123')),
              422, 'Monto con mas de dos decimales rechazado')
        check(client.post('/api/v1/loan-applications', json=dict(req, term_months=7)),
              422, 'Plazo no permitido rechazado')

    with SessionLocal() as db:
        assert db.get(Card, UUID(card['id'])) is not None
        assert db.get(LoanApplication, UUID(application['id'])) is not None
        new_loans = len(db.scalars(select(Loan).where(Loan.customer_id == customer_id)).all())
        assert new_loans == original_loans, 'Solicitar un prestamo NO debe crear un prestamo aprobado'
        audit_actions = set(db.scalars(select(AuditEvent.action).where(
            AuditEvent.entity_id.in_([UUID(card['id']), UUID(application['id'])])
        )).all())
        assert {'SYNTHETIC_CARD_ISSUED', 'SYNTHETIC_LOAN_APPLICATION_SUBMITTED'} <= audit_actions
        print('[OK] Persistencia en PostgreSQL y auditoria verificadas')
        print('[OK] No se ha aprobado ni desembolsado ningun prestamo')

    print('\nRESULTADO: PASO 2.10 - TARJETAS Y SOLICITUDES SINTETICAS VALIDADAS')
    print('AVISO: rutas sin autenticacion, solo en local. No exponer en Internet.')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, RuntimeError, httpx.HTTPError) as error:
        print(f'[ERROR] {error}', file=sys.stderr)
        sys.exit(1)
