from decimal import Decimal
import pytest
from app.services.financial_rules import money, request_fingerprint, assert_balanced
from app.services.transaction_schemas import AmountRequest, TransferRequest
from pydantic import ValidationError
from uuid import uuid4


def test_currency_decimal_precision():
    assert money(Decimal('12.50')) == Decimal('12.50')
    with pytest.raises(ValueError): money(Decimal('12.501'))
    with pytest.raises(ValueError): money(Decimal('10001'))


def test_stable_fingerprint_and_difference():
    kw = dict(kind='TRANSFER', accounts=['a', 'b'], amount=Decimal('10.00'), currency='PEN')
    assert request_fingerprint(**kw) == request_fingerprint(**kw)
    assert request_fingerprint(**kw) != request_fingerprint(**dict(kw, amount=Decimal('11.00')))


def test_balancing_rejects_unbalanced_or_cross_currency():
    assert_balanced([('DEBIT', Decimal('10'), 'PEN'), ('CREDIT', Decimal('10'), 'PEN')], 'PEN')
    with pytest.raises(ValueError): assert_balanced([('DEBIT', Decimal('10'), 'PEN'), ('CREDIT', Decimal('9'), 'PEN')], 'PEN')
    with pytest.raises(ValueError): assert_balanced([('DEBIT', Decimal('10'), 'PEN'), ('CREDIT', Decimal('10'), 'USD')], 'PEN')


def test_invalid_amount_and_key_rejected():
    with pytest.raises(ValidationError): AmountRequest(amount='0', currency='PEN', idempotency_key='unique-key-001')
    with pytest.raises(ValidationError): AmountRequest(amount='10.001', currency='PEN', idempotency_key='unique-key-001')
    with pytest.raises(ValidationError): AmountRequest(amount='10', currency='PEN', idempotency_key='bad')
    with pytest.raises(ValidationError): TransferRequest(amount='10', currency='EUR', idempotency_key='unique-key-001', source_account_id=uuid4(), target_account_id=uuid4())
