"""Deterministic presentation guardrails for Copilot human-facing fields.

Technical evidence is preserved verbatim in ``analysis.evidence``. Human-facing
fields are normalized to readable Spanish and deduplicated before the result is
returned/persisted. This complements (but does not replace) prompt/schema rules.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.copilot_schemas import CopilotAnalysis


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _canonical(value: str) -> str:
    value = _fold(value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        key = _canonical(value)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _looks_technical(value: str) -> bool:
    stripped = value.strip()
    if re.search(r"\b[a-z][a-z0-9_]{2,}\s*=\s*[^ ]+", stripped, re.I):
        return True
    # A standalone/internal snake_case token is technical; ordinary prose is not.
    tokens = re.findall(r"\b[a-z][a-z0-9_]{2,}\b", stripped, re.I)
    return any("_" in token for token in tokens)


def _risk_text(value: str) -> str:
    folded = _fold(value)

    ratio = re.search(
        r"(?:quality_gates_passed|quality_passed)=(\d+)\s*/\s*(\d+)",
        value,
        re.I,
    )
    if ratio:
        passed = int(ratio.group(1))
        total = int(ratio.group(2))
        failed = max(total - passed, 0)
        if failed:
            suffix = (
                "un control requiere revisión"
                if failed == 1
                else f"{failed} controles requieren revisión"
            )
            return (
                "La ejecución no superó todos los controles de calidad: "
                f"aprobó {passed} de {total} y {suffix}."
            )

    total_match = re.search(r"quality_total=(\d+)", value, re.I)
    passed_match = re.search(r"quality_passed=(\d+)", value, re.I)
    failed_match = re.search(r"quality_failed=(\d+)", value, re.I)
    if total_match and passed_match and failed_match:
        total = int(total_match.group(1))
        passed = int(passed_match.group(1))
        failed = int(failed_match.group(1))
        if failed > 0:
            suffix = (
                "un control requiere revisión"
                if failed == 1
                else f"{failed} controles requieren revisión"
            )
            return (
                "La ejecución no superó todos los controles de calidad: "
                f"aprobó {passed} de {total} y {suffix}."
            )

    natural_ratio = re.search(
        r"(?:aprobo|aprob[oó])\s+(\d+)\s+de\s+(\d+)\s+controles",
        folded,
    )
    if natural_ratio and "no super" in folded:
        passed = int(natural_ratio.group(1))
        total = int(natural_ratio.group(2))
        failed = max(total - passed, 0)
        if failed:
            suffix = (
                "un control requiere revisión"
                if failed == 1
                else f"{failed} controles requieren revisión"
            )
            return (
                "La ejecución no superó todos los controles de calidad: "
                f"aprobó {passed} de {total} y {suffix}."
            )

    if "quality_gate_failed" in folded:
        return "La ejecución no superó todos los controles de calidad."

    if "moneda no permitid" in folded or "failure_reason=moneda" in folded:
        return "Un registro fue aislado porque contiene una moneda no permitida."

    if (
        "para evitar que un dato invalido llegara a la version gold" in folded
        or "no llegara a la version gold" in folded
        or "no fue incorporado a la version gold" in folded
    ):
        return "El registro inválido quedó aislado y no fue incorporado a la versión Gold."

    quarantined = re.search(
        r"(?:rows_quarantined|records_quarantined|quarantine_records)=(\d+)",
        value,
        re.I,
    )
    if quarantined:
        amount = int(quarantined.group(1))
        return (
            "Un registro fue aislado durante el control de calidad."
            if amount == 1
            else f"{amount} registros fueron aislados durante el control de calidad."
        )

    if (
        "no reemplazo la version gold vigente" in folded
        or "gold_protected=true" in folded
        or "is_current_gold=false" in folded
        or ("current_gold" in folded and "published" in folded)
    ):
        return (
            "La versión Gold vigente se mantuvo protegida y no fue "
            "reemplazada por esta ejecución."
        )

    if "gold_published=false" in folded:
        return "La ejecución no publicó una nueva versión Gold."

    if (
        "transaction_total_not_equal_ledger_total" in folded
        or "reconciliation_status_mismatch" in folded
        or "reconciliation_status=mismatch" in folded
    ):
        return "Los movimientos y los asientos contables no coinciden y requieren revisión."

    if "identity_result=mismatch" in folded:
        return "La información de identidad presenta una inconsistencia que requiere revisión."

    if "onboarding_status=pending" in folded:
        return "La verificación de identidad permanece pendiente de revisión."

    if "human_decision=not_yet_performed" in folded:
        return "Todavía no se ha registrado una decisión humana para este caso."

    if "operation_status=unknown" in folded:
        return "El estado final de la operación no está confirmado."

    if _looks_technical(value):
        return ""

    return value.strip()


def _risk_items(
    values: list[str],
    category: str,
    evidence: list[str],
) -> list[str]:
    items = _dedupe([_risk_text(value) for value in values])

    # Enrich human-facing alerts from verified technical evidence when the
    # model omitted an important containment fact. This is deterministic and
    # does not invent information: it only fires for a failed quality run with
    # one or more quarantined rows.
    technical_context = " ".join(evidence)
    folded_context = _fold(technical_context)
    quarantined_match = re.search(
        r"(?:rows_quarantined|records_quarantined|quarantine_records)=(\d+)",
        technical_context,
        re.I,
    )
    failed_quality_run = (
        category in {"DATA_QUALITY", "QUARANTINE"}
        and (
            "status=quality_gate_failed" in folded_context
            or "quality_failed=" in folded_context
            or "gold_published=false" in folded_context
        )
    )

    if quarantined_match and failed_quality_run:
        amount = int(quarantined_match.group(1))
        if amount > 0:
            containment = (
                "El registro inválido quedó aislado y no fue incorporado "
                "a la versión Gold."
                if amount == 1
                else (
                    f"Los {amount} registros inválidos quedaron aislados y no "
                    "fueron incorporados a la versión Gold."
                )
            )
            if _canonical(containment) not in {
                _canonical(existing) for existing in items
            }:
                items.append(containment)

    has_precise_quality = any(
        item.startswith("La ejecución no superó todos los controles de calidad:")
        for item in items
    )
    has_specific_quarantine = any("moneda no permitid" in _fold(item) for item in items)

    filtered: list[str] = []
    for item in items:
        if has_precise_quality and item == "La ejecución no superó todos los controles de calidad.":
            continue
        if has_specific_quarantine and item == "Un registro fue aislado durante el control de calidad.":
            continue
        filtered.append(item)

    def priority(item: str) -> int:
        folded = _fold(item)
        if item.startswith("La ejecución no superó todos los controles de calidad:"):
            return 10
        if "moneda no permitid" in folded:
            return 20
        if "no fue incorporado a la version gold" in folded:
            return 30
        if "version gold vigente se mantuvo protegida" in folded:
            return 40
        return 50

    return sorted(filtered, key=priority)


def _pending_text(value: str) -> str:
    folded = _fold(value)

    if "identificador" in folded and ("cuarentena" in folded or "quarantine" in folded):
        return "Identificar el registro aislado que originó la observación."

    if "valor exacto" in folded and ("currency" in folded or "moneda" in folded):
        return "Confirmar el valor de moneda que fue rechazado."

    if "record_validation" in folded or (
        "definicion" in folded and "version" in folded and "regla" in folded
    ):
        return (
            "Confirmar la definición y versión de la regla de validación del "
            "registro aplicada en esta ejecución."
        )

    if "normalizaci" in folded or "lista blanca" in folded or "monedas permitidas" in folded:
        return "Confirmar el catálogo de monedas permitidas y las reglas de validación."

    if "fecha" in folded and "hora" in folded or "timestamp" in folded or "usuario/servicio" in folded:
        return "Confirmar la fecha, hora y origen que inició la ejecución."

    if "impacto" in folded or "downstream" in folded or ("proceso" in folded and "reporte" in folded):
        return "Verificar si algún proceso, reporte o tablero podría verse afectado."

    if "re-procesamiento" in folded or "reprocesamiento" in folded or "nuevo procesamiento" in folded:
        return (
            "Confirmar si existe un nuevo procesamiento programado o ejecuciones "
            "anteriores para comparar."
        )

    if (
        "accion esperada" in folded
        or "equipo de negocio" in folded
        or ("correcci" in folded and "manual" in folded)
    ):
        return (
            "Definir con el equipo responsable si el dato debe corregirse "
            "automáticamente o mediante revisión manual."
        )

    if "logs" in folded or "trazas" in folded or "auditoria" in folded:
        return (
            "Revisar el registro técnico de la ejecución para identificar "
            "errores y tiempos del proceso."
        )

    if _looks_technical(value):
        return ""

    return value.strip()


def _pending_items(values: list[str], category: str, evidence: list[str]) -> list[str]:
    items = _dedupe([_pending_text(value) for value in values])

    technical_context = " ".join(evidence)
    data_quality = category in {"DATA_QUALITY", "QUARANTINE"} or any(
        token in _fold(technical_context)
        for token in ("quality_", "quarantine_", "record_validation")
    )

    if data_quality:
        additions = [
            "Confirmar la fecha, hora y origen que inició la ejecución.",
            (
                "Definir con el equipo responsable si el dato debe corregirse "
                "automáticamente o mediante revisión manual."
            ),
        ]
        for item in additions:
            if _canonical(item) not in {_canonical(existing) for existing in items}:
                items.append(item)

    return _dedupe(items)


def sanitize_human_facing_analysis(analysis: CopilotAnalysis) -> CopilotAnalysis:
    """Return a copy with deterministic human-facing cleanup.

    ``evidence`` is deliberately preserved verbatim for auditability.
    """

    risk_flags = _risk_items(
        list(analysis.risk_flags),
        analysis.category,
        list(analysis.evidence),
    )
    missing_information = _pending_items(
        list(analysis.missing_information),
        analysis.category,
        list(analysis.evidence),
    )

    return analysis.model_copy(
        update={
            "risk_flags": risk_flags,
            "missing_information": missing_information,
        }
    )
