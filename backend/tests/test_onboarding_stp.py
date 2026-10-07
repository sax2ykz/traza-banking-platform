from app.services.onboarding_stp import (
    RULE_VERSION,
    evaluate_onboarding_stp,
)


def test_match_limpio_es_verified_automatico():
    result = evaluate_onboarding_stp(
        verification_result="MATCH",
        document_status="CURRENT",
        matched_name=True,
        matched_birth_date=True,
    )

    assert result.decision == "VERIFIED"
    assert result.reason == "LOW_RISK_IDENTITY_MATCH"
    assert result.automatic is True
    assert result.rule_version == RULE_VERSION
    assert result.priority == "LOW"
    assert result.severity == "LOW"
    assert result.sla_hours == 0


def test_mismatch_va_a_revision():
    result = evaluate_onboarding_stp(
        verification_result="MISMATCH",
        document_status="CURRENT",
        matched_name=False,
        matched_birth_date=True,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "IDENTITY_MISMATCH"
    assert result.automatic is False
    assert result.priority == "HIGH"
    assert result.severity == "HIGH"


def test_documento_no_vigente_va_a_revision():
    result = evaluate_onboarding_stp(
        verification_result="NOT_CURRENT",
        document_status="NOT_CURRENT",
        matched_name=True,
        matched_birth_date=True,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "DOCUMENT_NOT_CURRENT"
    assert result.automatic is False


def test_identidad_no_encontrada_va_a_revision():
    result = evaluate_onboarding_stp(
        verification_result="NOT_FOUND",
        document_status=None,
        matched_name=False,
        matched_birth_date=False,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "IDENTITY_NOT_FOUND"
    assert result.automatic is False


def test_match_con_evidencia_incompleta_falla_cerrado():
    result = evaluate_onboarding_stp(
        verification_result="MATCH",
        document_status="CURRENT",
        matched_name=True,
        matched_birth_date=True,
        evidence_complete=False,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "INSUFFICIENT_EVIDENCE"
    assert result.automatic is False
    assert result.priority == "HIGH"
    assert result.severity == "HIGH"


def test_match_con_alerta_bloqueante_no_se_autoaprueba():
    result = evaluate_onboarding_stp(
        verification_result="MATCH",
        document_status="CURRENT",
        matched_name=True,
        matched_birth_date=True,
        has_blocking_alerts=True,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "BUSINESS_RULE_ALERT"
    assert result.automatic is False


def test_estado_inconsistente_nunca_es_verified():
    result = evaluate_onboarding_stp(
        verification_result="MATCH",
        document_status=None,
        matched_name=True,
        matched_birth_date=True,
    )

    assert result.decision == "REVIEW_REQUIRED"
    assert result.reason == "INSUFFICIENT_EVIDENCE"
    assert result.automatic is False
