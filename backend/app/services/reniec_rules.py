"""Business rules for the synthetic RENIEC Simulator.

Pure functions are kept separate from HTTP and persistence so identity
classification can be regression-tested without a live database.
"""
from datetime import date


def normalize_name(value: str) -> str:
    return " ".join(value.upper().split())


def evaluate_identity(
    *,
    customer_full_name: str,
    claimed_birth_date: date,
    registry_full_name: str | None,
    registry_birth_date: date | None,
    registry_document_status: str | None,
) -> tuple[str, bool, bool]:
    if registry_full_name is None:
        return "NOT_FOUND", False, False

    matched_name = (
        normalize_name(registry_full_name)
        == normalize_name(customer_full_name)
    )

    matched_birth_date = (
        registry_birth_date == claimed_birth_date
    )

    if registry_document_status != "CURRENT":
        return "NOT_CURRENT", matched_name, matched_birth_date

    if matched_name and matched_birth_date:
        return "MATCH", True, True

    return "MISMATCH", matched_name, matched_birth_date