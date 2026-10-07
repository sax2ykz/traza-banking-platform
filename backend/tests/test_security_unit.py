"""Security regression: no DB records created by isolated tests."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.security import hash_password, valid_password, verify_password, verify_customer_access
from app.security_models import AppUser


def user(role='CUSTOMER', customer_id=None):
    return AppUser(id=uuid4(), email='synthetic@example.invalid', role=role,
                   customer_id=customer_id, active=True, password_hash='unused')


@pytest.mark.parametrize('weak', ['short', 'longbutnosymbolA123', 'lowerlowerlower3!', 'UPPERUPPERUPPER3!'])
def test_weak_passwords_rejected(weak):
    assert not valid_password(weak)


def test_password_hashing_and_mismatch():
    strong = 'SuperSecret!23456Synthetic'
    encoded = hash_password(strong)
    assert encoded != strong
    assert verify_password(strong, encoded)
    assert not verify_password('NotThePassword!123', encoded)


def test_customer_cannot_access_other_customer():
    first = uuid4()
    principal = user(customer_id=first)
    verify_customer_access(principal, first)
    with pytest.raises(HTTPException) as err:
        verify_customer_access(principal, uuid4())
    assert err.value.status_code == 403


def test_nonadmin_cannot_bypass_ownership_and_admin_only_when_authorized():
    admin = user(role='ADMIN')
    verify_customer_access(admin, uuid4(), allow_admin=True)
    with pytest.raises(HTTPException):
        verify_customer_access(admin, uuid4(), allow_admin=False)
