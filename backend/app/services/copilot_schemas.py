"""Structured contracts for BancoCloud Operational Copilot."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CopilotCategory = Literal[
    "DATA_QUALITY",
    "QUARANTINE",
    "RECONCILIATION",
    "OPERATION",
    "ONBOARDING",
    "OTHER",
]

CopilotSourceEntityType = Literal[
    "DATAOPS_RUN",
    "BANKING_OPERATION",
    "ONBOARDING",
    "RECONCILIATION",
    "OTHER",
]


class OperationalExceptionContext(BaseModel):
    """Minimal operational context sent to the AI service."""

    model_config = ConfigDict(extra="forbid")

    exception_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1500)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CopilotAnalysis(BaseModel):
    """Strict structured response expected from GPT-5-mini."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        description=(
            "Resumen operativo en español claro para lectura humana; "
            "sin copiar evidencia técnica en formato key=value."
        )
    )
    category: CopilotCategory
    evidence: list[str] = Field(
        description=(
            "Evidencia técnica respaldada por el contexto. Este es el "
            "único campo donde pueden conservarse identificadores, "
            "snake_case, códigos y expresiones key=value."
        )
    )
    risk_flags: list[str] = Field(
        description=(
            "Entre 3 y 5 alertas distintas cuando la evidencia lo permita, "
            "cubriendo resultado, hallazgo, contención e impacto/protección "
            "sin fragmentar una misma idea. No usar key=value, snake_case "
            "ni repetir el mismo hallazgo con frases equivalentes."
        )
    )
    missing_information: list[str] = Field(
        description=(
            "Puntos concretos que deben verificarse, redactados en lenguaje "
            "natural. Cuando sea pertinente, incluir metadatos operativos "
            "como fecha/hora/origen y criterio de corrección con el equipo "
            "responsable. No usar nombres internos como record_validation "
            "ni repetir alertas."
        )
    )
    recommended_next_step: str = Field(
        description=(
            "Siguiente paso de revisión o verificación, en lenguaje claro "
            "y sin ordenar acciones sensibles o irreversibles."
        )
    )
    confidence: float
    human_review_required: bool

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )
        return value


class CopilotRunResult(BaseModel):
    """Application envelope used by the Foundry service."""

    prompt_version: str
    model: str
    analysis: CopilotAnalysis


class CopilotAdminAnalysisRequest(BaseModel):
    """Administrative request to analyze one exception."""

    model_config = ConfigDict(extra="forbid")

    source_entity_type: CopilotSourceEntityType
    source_entity_id: UUID | None = None
    context: OperationalExceptionContext


class CopilotAdminAnalysisResponse(BaseModel):
    correlation_id: UUID
    status: Literal["COMPLETED"]
    prompt_version: str
    model: str
    analysis: CopilotAnalysis
    human_review_status: Literal["PENDING"]


class CopilotHumanReviewRequest(BaseModel):
    """Human review of a previously generated Copilot analysis."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["ACKNOWLEDGED", "ESCALATED"]
    notes: str = Field(default="", max_length=500)


class CopilotHumanReviewResponse(BaseModel):
    correlation_id: UUID
    decision: Literal["ACKNOWLEDGED", "ESCALATED"]
    reviewed_by: UUID
    human_review_status: Literal["COMPLETED"]
