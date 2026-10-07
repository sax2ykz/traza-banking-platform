"""Pure, independently testable policies for a SYNTHETIC local bank demo."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

CENT = Decimal('0.01')


def money(value: Decimal) -> Decimal:
    value = Decimal(str(value))
    if not value.is_finite() or value <= 0 or value > Decimal('10000.00'):
        raise ValueError('The simulated amount must be between 0.01 and 10000.00')
    if value != value.quantize(CENT):
        raise ValueError('At most two decimal places are allowed')
    return value.quantize(CENT)


def request_fingerprint(*, kind: str, accounts: list[str], amount: Decimal, currency: str) -> str:
    """Canonical business parameters; the key is checked separately."""
    doc = {'operation': kind, 'accounts': accounts, 'amount': format(amount, '.2f'), 'currency': currency}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def assert_balanced(entries: list[tuple[str, Decimal, str]], currency: str) -> None:
    """Balanced nominal entries in the SAME currency; avoid mixing customer direction with GL direction."""
    if len(entries) != 2 or any(c != currency or a <= 0 for _, a, c in entries):
        raise ValueError('Exactly two positive, single-currency entries are required')
    debits = sum((amount for direction, amount, _ in entries if direction == 'DEBIT'), Decimal('0'))
    credits = sum((amount for direction, amount, _ in entries if direction == 'CREDIT'), Decimal('0'))
    if debits <= 0 or debits != credits:
        raise ValueError('Unbalanced journal')
