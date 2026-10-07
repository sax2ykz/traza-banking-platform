"""Local-only end-to-end security demonstration, never use real IDs or PII.
Uses a development-only bootstrap admin, generated disposable customer secrets,
and simulated manual verification metadata. No real KYC occurs.
"""
import argparse
import getpass
import secrets
import sys
from pathlib import Path
from uuid import uuid4
import httpx

BASE = 'http://127.0.0.1:8000'
STRONG_SUFFIX = 'Xy7!'  # Generated customer passwords never printed or persisted.


def check(res, code, label):
    if res.status_code != code:
        raise RuntimeError(f'{label}: expected HTTP {code}, got {res.status_code}: {res.text[:200]}')
    print(f'[OK] {label}: HTTP {code}')
    return res.json() if res.content else None


def login(client, email, password):
    res = client.post('/api/v1/auth/token', data={'username': email, 'password': password})
    return check(res, 200, 'Login synthetic user')['access_token']


def auth_header(token):
    return {'Authorization': f'Bearer {token}'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--solo-local-sintetico', action='store_true')
    args = parser.parse_args()
    if not args.solo_local_sintetico:
        sys.exit('Use --solo-local-sintetico for this synthetic integration test')
    pwd_admin = getpass.getpass('Synthetic local admin password (hidden): ')
    with httpx.Client(base_url=BASE, timeout=20) as client:
        check(client.get('/health/db'), 200, 'FastAPI + PostgreSQL ready')
        check(client.get('/api/v1/customers'), 401, 'Anonymous cannot list customer data')
        check(client.post('/api/v1/auth/token', data={
            'username': 'admin@bancocloud.invalid', 'password': 'DefinitelyWrong!123'
        }), 401, 'Invalid password rejected')
        admin_token = login(client, 'admin@bancocloud.invalid', pwd_admin)
        admin = auth_header(admin_token)
        check(client.get('/api/v1/auth/me', headers=admin), 200, 'Admin profile available')
        uid = uuid4().hex[:10].lower()
        first_email = f'cliente-{uid}@example.invalid'
        second_email = f'cliente-dos-{uid}@example.invalid'
        # Disposable, strong, independent passwords.
        pass_one, pass_two = secrets.token_urlsafe(24) + STRONG_SUFFIX, secrets.token_urlsafe(24) + STRONG_SUFFIX
        first = check(client.post('/api/v1/auth/register', json={
            'full_name': 'Cliente de prueba Alfa', 'email': first_email,
            'region': 'Lima', 'password': pass_one,
        }), 201, 'First synthetic customer registered as PENDING')
        second = check(client.post('/api/v1/auth/register', json={
            'full_name': 'Cliente de prueba Beta', 'email': second_email,
            'region': 'Arequipa', 'password': pass_two,
        }), 201, 'Second synthetic customer registered as PENDING')
        token_one = login(client, first_email, pass_one)
        token_two = login(client, second_email, pass_two)
        one, two = auth_header(token_one), auth_header(token_two)
        check(client.get('/api/v1/admin/onboarding/pending', headers=one), 403,
              'Customer cannot list administrative onboarding queue')
        check(client.post(f"/api/v1/admin/onboarding/{first['customer_id']}/review", headers=one,
                          json={'decision': 'VERIFIED', 'evidence_ref': f'SIM-EVID-{uid}',
                                'document_checked': True, 'data_consistent': True}), 403,
              'Customer cannot approve own identity')
        check(client.post('/api/v1/accounts', headers=one, json={
            'customer_id': first['customer_id'], 'account_type': 'SAVINGS', 'currency': 'PEN',
        }), 409, 'Pending customer cannot open account')
        check(client.post(f"/api/v1/admin/onboarding/{first['customer_id']}/review", headers=admin,
                          json={'decision': 'VERIFIED', 'evidence_ref': f'SIM-EVID-{uid}',
                                'document_checked': False, 'data_consistent': True}), 422,
              'Incomplete simulated verification checklist rejected')
        for registered in (first, second):
            check(client.post(f"/api/v1/admin/onboarding/{registered['customer_id']}/review", headers=admin,
                              json={'decision': 'VERIFIED', 'evidence_ref': f'SIM-EVID-{uid}',
                                    'document_checked': True, 'data_consistent': True,
                                    'notes': 'Only fictitious local test metadata'}), 200,
                  'Administrator records simulated identity review with audit')
        account_one = check(client.post('/api/v1/accounts', headers=one, json={
            'customer_id': first['customer_id'], 'account_type': 'SAVINGS', 'currency': 'PEN',
        }), 201, 'Customer A opens own account')
        account_two = check(client.post('/api/v1/accounts', headers=two, json={
            'customer_id': second['customer_id'], 'account_type': 'SAVINGS', 'currency': 'PEN',
        }), 201, 'Customer B opens own account')
        check(client.get(f"/api/v1/accounts/{account_one['id']}", headers=two), 403,
              'Customer B cannot read account A')
        check(client.get(f"/api/v1/accounts/{account_one['id']}/movements", headers=two), 403,
              'Customer B cannot read account A transaction history')
        check(client.get(f"/api/v1/customers/{first['customer_id']}", headers=two), 403,
              'Customer B cannot read personal details of customer A')
        check(client.post('/api/v1/loan-applications', headers=two,
                          json={'customer_id': first['customer_id'], 'requested_amount': '1000.00',
                                'currency': 'PEN', 'term_months': 12, 'purpose': 'Fictitious consumer test'}), 403,
              'Customer B cannot submit loan for customer A')
        check(client.post('/api/v1/cards', headers=two,
                          json={'account_id': account_one['id']}), 403,
              'Customer B cannot issue card against account A')
        check(client.post('/api/v1/operations/deposit', headers=one, json={
            'account_id': account_one['id'], 'amount': '80.00', 'currency': 'PEN',
            'idempotency_key': f'dep{uid}a',
        }), 201, 'Authenticated customer A performs synthetic deposit')
        check(client.post('/api/v1/operations/withdraw', headers=two, json={
            'account_id': account_one['id'], 'amount': '10.00', 'currency': 'PEN',
            'idempotency_key': f'cross{uid}b',
        }), 403, 'Customer B cannot withdraw from account A')
        trans = check(client.post('/api/v1/operations/transfer', headers=one, json={
            'source_account_id': account_one['id'], 'target_account_id': account_two['id'],
            'amount': '20.00', 'currency': 'PEN', 'idempotency_key': f'trans{uid}a',
        }), 201, 'Customer A sends permitted synthetic transfer')
        if str(account_two['id']) in trans.get('balances_after', {}):
            raise AssertionError('Privacy bug: transfer result exposed destination account balance')
        print('[OK] Transfer response hides other customer balance')
        check(client.get(f"/api/v1/accounts/{account_two['id']}", headers=two), 200,
              'Customer B can read own account')
        print('RESULT: LOCAL AUTH + HUMAN REVIEW SIMULATION + OWNERSHIP REGRESSION PASSED')
        print('NOTE: This is synthetic KYC only. Local HS256 JWT is NOT an enterprise IAM replacement.')


if __name__ == '__main__':
    main()
