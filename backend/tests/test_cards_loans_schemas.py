"""Isolated validation tests, safe without running PostgreSQL."""
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.services.cards_loans_schemas import CardCreate, LoanApplicationCreate


def valid_request(**overrides):
    payload = dict(customer_id=uuid4(), requested_amount='2000.00', currency='PEN',
                   term_months=12, purpose='Consumo personal simulado',
                   disbursement_account_id=uuid4())
    return LoanApplicationCreate(**dict(payload, **overrides))


def test_valid_synthetic_loan_application():
    app = valid_request()
    assert str(app.requested_amount) == '2000.00' and app.term_months == 12


@pytest.mark.parametrize('bad', ['0', '-5', '499.99', '50000.01', '100.001', 'NaN'])
def test_invalid_amounts_rejected(bad):
    with pytest.raises(ValidationError):
        valid_request(requested_amount=bad)


@pytest.mark.parametrize('bad', [1, 5, 7, 61])
def test_invalid_terms_rejected(bad):
    with pytest.raises(ValidationError):
        valid_request(term_months=bad)


def test_invalid_currency_and_purpose_rejected():
    with pytest.raises(ValidationError):
        valid_request(currency='EUR')
    with pytest.raises(ValidationError):
        valid_request(purpose='')


def test_card_contract_does_not_accept_sensitive_fields():
    assert list(CardCreate.model_fields) == ['account_id']
    assert CardCreate(account_id=uuid4()).account_id
