import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataops.pipeline_core import validate_operation, validate_transaction


def test_dataops_accepts_loan_disbursement_transaction():
    account_id = uuid4()
    operation_id = uuid4()
    loan_id = uuid4()

    row = {
        "account_id": account_id,
        "loan_id": loan_id,
        "operation_id": operation_id,
        "currency": "PEN",
        "direction": "CREDIT",
        "transaction_type": "LOAN_DISBURSEMENT",
        "amount": "1500.00",
        "balance_after": "2400.00",
    }
    ctx = {
        "accounts": {account_id},
        "operations": {operation_id},
    }

    assert validate_transaction(row, ctx) == []


def test_dataops_rejects_loan_disbursement_without_loan_lineage():
    account_id = uuid4()
    operation_id = uuid4()
    row = {
        "account_id": account_id,
        "loan_id": None,
        "operation_id": operation_id,
        "currency": "PEN",
        "direction": "CREDIT",
        "transaction_type": "LOAN_DISBURSEMENT",
        "amount": "1500.00",
        "balance_after": "2400.00",
    }
    ctx = {"accounts": {account_id}, "operations": {operation_id}}

    assert "loan_id: requerido para desembolso de préstamo" in validate_transaction(row, ctx)


def test_dataops_accepts_loan_disbursement_operation_shape():
    account_id = uuid4()
    row = {
        "operation_type": "LOAN_DISBURSEMENT",
        "source_account_id": None,
        "target_account_id": account_id,
        "currency": "PEN",
        "status": "COMPLETED",
        "amount": "1500.00",
    }
    ctx = {"accounts": {account_id}}

    assert validate_operation(row, ctx) == []


def test_dataops_rejects_loan_disbursement_with_invalid_operation_shape():
    account_id = uuid4()
    row = {
        "operation_type": "LOAN_DISBURSEMENT",
        "source_account_id": account_id,
        "target_account_id": uuid4(),
        "currency": "PEN",
        "status": "COMPLETED",
        "amount": "1500.00",
    }
    ctx = {"accounts": {account_id}}

    errors = validate_operation(row, ctx)
    assert "source_account_id: debe ser nulo para desembolso de préstamo" in errors
    assert "target_account_id: cuenta destino inexistente" in errors
