"""Live schema checks against the user's Docker database; no INSERTs or DELETEs."""
from sqlalchemy import inspect
from app.database import engine
from app.models import Base

EXPECTED = {
    "accounts", "audit_events", "banking_operations", "cards", "customers",
    "ledger_entries", "loan_applications", "loan_installments", "loan_payments",
    "loans", "transactions",
}


def test_all_eleven_mappings_present():
    assert set(Base.metadata.tables) == EXPECTED


def test_real_database_contains_all_tables_and_model_columns():
    inspector = inspect(engine)
    actual = set(inspector.get_table_names(schema="public"))
    assert EXPECTED <= actual
    for name, table in Base.metadata.tables.items():
        db_columns = {column["name"] for column in inspector.get_columns(name)}
        mapped_columns = set(table.columns.keys())
        assert mapped_columns <= db_columns, (name, mapped_columns - db_columns)


def test_critical_foreign_keys_present_in_real_database():
    inspector = inspect(engine)
    expected = {
        "transactions": [("operation_id", "banking_operations")],
        "ledger_entries": [("operation_id", "banking_operations")],
        "loan_applications": [("disbursement_account_id", "accounts")],
        "loans": [
            ("loan_application_id", "loan_applications"),
            ("approved_by_user_id", "app_users"),
            ("disbursement_account_id", "accounts"),
            ("disbursement_operation_id", "banking_operations"),
        ],
        "loan_payments": [("installment_id", "loan_installments")],
    }
    for table, requirements in expected.items():
        fks = inspector.get_foreign_keys(table)
        for field, target in requirements:
            assert any(
                field in fk["constrained_columns"]
                and fk["referred_table"] == target
                for fk in fks
            ), (table, field, target)
