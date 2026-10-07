from datetime import date

from app.services.reniec_rules import (
    evaluate_identity,
    normalize_name,
)


def test_normalize_name_is_case_and_space_insensitive():
    assert (
        normalize_name("  Cliente   Demo BancoCloud ")
        == "CLIENTE DEMO BANCOCLOUD"
    )


def test_reniec_match():
    result, matched_name, matched_birth_date = evaluate_identity(
        customer_full_name="Cliente Demo BancoCloud",
        claimed_birth_date=date(2001, 5, 14),
        registry_full_name="Cliente Demo BancoCloud",
        registry_birth_date=date(2001, 5, 14),
        registry_document_status="CURRENT",
    )

    assert result == "MATCH"
    assert matched_name is True
    assert matched_birth_date is True


def test_reniec_mismatch_birth_date():
    result, matched_name, matched_birth_date = evaluate_identity(
        customer_full_name="Cliente Demo BancoCloud",
        claimed_birth_date=date(2000, 1, 1),
        registry_full_name="Cliente Demo BancoCloud",
        registry_birth_date=date(2001, 5, 14),
        registry_document_status="CURRENT",
    )

    assert result == "MISMATCH"
    assert matched_name is True
    assert matched_birth_date is False


def test_reniec_mismatch_name():
    result, matched_name, matched_birth_date = evaluate_identity(
        customer_full_name="Nombre Diferente",
        claimed_birth_date=date(2001, 5, 14),
        registry_full_name="Cliente Demo BancoCloud",
        registry_birth_date=date(2001, 5, 14),
        registry_document_status="CURRENT",
    )

    assert result == "MISMATCH"
    assert matched_name is False
    assert matched_birth_date is True


def test_reniec_not_found():
    result, matched_name, matched_birth_date = evaluate_identity(
        customer_full_name="Cliente Demo BancoCloud",
        claimed_birth_date=date(2001, 5, 14),
        registry_full_name=None,
        registry_birth_date=None,
        registry_document_status=None,
    )

    assert result == "NOT_FOUND"
    assert matched_name is False
    assert matched_birth_date is False


def test_reniec_not_current_has_priority():
    result, matched_name, matched_birth_date = evaluate_identity(
        customer_full_name="Carlos Mendoza Demo",
        claimed_birth_date=date(1995, 3, 21),
        registry_full_name="Carlos Mendoza Demo",
        registry_birth_date=date(1995, 3, 21),
        registry_document_status="NOT_CURRENT",
    )

    assert result == "NOT_CURRENT"
    assert matched_name is True
    assert matched_birth_date is True