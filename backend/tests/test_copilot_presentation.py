from app.services.copilot_presentation import sanitize_human_facing_analysis
from app.services.copilot_schemas import CopilotAnalysis


def test_data_quality_human_fields_are_clean_and_evidence_is_preserved():
    analysis = CopilotAnalysis(
        summary="Ejecución con observaciones de calidad.",
        category="DATA_QUALITY",
        evidence=[
            "run_id=test-run",
            "quality_total=16",
            "quality_passed=15",
            "quality_failed=1",
            "status=QUALITY_GATE_FAILED",
            "rows_quarantined=1",
            "quarantine_rule_name=record_validation",
        ],
        risk_flags=[
            "quality_total=16; quality_passed=15; quality_failed=1",
            "La ejecución no superó todos los controles de calidad.",
            "quarantine_records=1",
            "El registro aislado contiene una moneda no permitida.",
            "La ejecución con observaciones no reemplazó la versión Gold vigente.",
        ],
        missing_information=[
            "Identificar el registro de cuarentena.",
            "Confirmar el valor exacto de moneda rechazado.",
            "Definición y versión de la regla record_validation.",
            "Confirmar el catálogo de monedas permitidas.",
            "Confirmar el catálogo de monedas permitidas.",
        ],
        recommended_next_step="Revisar el registro aislado.",
        confidence=0.85,
        human_review_required=True,
    )

    cleaned = sanitize_human_facing_analysis(analysis)

    assert any("aprobó 15 de 16" in item for item in cleaned.risk_flags)
    assert any("moneda no permitida" in item for item in cleaned.risk_flags)
    assert any("no fue incorporado" in item for item in cleaned.risk_flags)
    assert any("Gold vigente" in item for item in cleaned.risk_flags)
    assert all("=" not in item for item in cleaned.risk_flags)
    assert all("record_validation" not in item for item in cleaned.missing_information)
    assert any("fecha, hora y origen" in item for item in cleaned.missing_information)
    assert any("equipo responsable" in item for item in cleaned.missing_information)
    assert len(cleaned.missing_information) == len(set(cleaned.missing_information))
    assert cleaned.evidence == analysis.evidence


def test_unknown_technical_tokens_do_not_leak_to_human_lists():
    analysis = CopilotAnalysis(
        summary="Caso de prueba.",
        category="OTHER",
        evidence=["internal_rule_name=x_rule"],
        risk_flags=["internal_rule_name=x_rule", "Revisión humana requerida."],
        missing_information=["internal_field_name=x_value", "Confirmar información con el responsable."],
        recommended_next_step="Revisar.",
        confidence=0.5,
        human_review_required=True,
    )

    cleaned = sanitize_human_facing_analysis(analysis)

    assert cleaned.risk_flags == ["Revisión humana requerida."]
    assert cleaned.missing_information == ["Confirmar información con el responsable."]
    assert cleaned.evidence == ["internal_rule_name=x_rule"]


def test_quality_containment_is_derived_from_evidence_when_model_omits_it():
    analysis = CopilotAnalysis(
        summary="Ejecución con observaciones de calidad.",
        category="DATA_QUALITY",
        evidence=[
            "status=QUALITY_GATE_FAILED",
            "rows_quarantined=1",
            "quality_total=16",
            "quality_passed=15",
            "quality_failed=1",
        ],
        risk_flags=[
            "La ejecución aprobó 15 de 16 controles de calidad.",
            "El registro aislado contiene una moneda no permitida.",
            "La versión Gold vigente se mantuvo protegida y no fue reemplazada por esta ejecución.",
        ],
        missing_information=[],
        recommended_next_step="Revisar el registro aislado.",
        confidence=0.85,
        human_review_required=True,
    )

    cleaned = sanitize_human_facing_analysis(analysis)

    assert any(
        item == "El registro inválido quedó aislado y no fue incorporado a la versión Gold."
        for item in cleaned.risk_flags
    )
    assert len(cleaned.risk_flags) == len(set(cleaned.risk_flags))
