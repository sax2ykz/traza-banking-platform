import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataops.pipeline_core import validate_operation


def _context():
    account_a = uuid4()
    account_b = uuid4()
    return account_a, account_b, {
        "accounts": {account_a, account_b},
        "customers": set(),
        "operations": set(),
        "loans": set(),
        "installments": set(),
    }


def test_internal_transfer_requires_two_existing_distinct_accounts():
    source, target, ctx = _context()

    row = {
        "operation_type": "TRANSFER",
        "source_account_id": source,
        "target_account_id": target,
        "amount": "10.00",
        "currency": "PEN",
        "status": "COMPLETED",
    }

    assert validate_operation(row, ctx) == []

    row["target_account_id"] = source
    errors = validate_operation(row, ctx)
    assert "target_account_id: debe diferir de la cuenta origen" in errors


def test_interbank_transfer_requires_source_and_null_internal_target():
    source, target, ctx = _context()

    row = {
        "operation_type": "INTERBANK_TRANSFER",
        "source_account_id": source,
        "target_account_id": None,
        "amount": "10.00",
        "currency": "PEN",
        "status": "COMPLETED",
    }

    assert validate_operation(row, ctx) == []

    row["target_account_id"] = target
    errors = validate_operation(row, ctx)
    assert (
        "target_account_id: debe ser nulo para transferencia interbancaria"
        in errors
    )
