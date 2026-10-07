"""Microsoft Foundry integration for BancoCloud Operational Copilot."""

import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from app.services.copilot_prompts import ACTIVE_PROMPT, PROMPT_VERSION
from app.services.copilot_presentation import sanitize_human_facing_analysis
from app.services.copilot_schemas import (
    CopilotAnalysis,
    CopilotRunResult,
    OperationalExceptionContext,
)


DEFAULT_MODEL = "gpt-5-mini"


class CopilotConfigurationError(RuntimeError):
    """Raised when required Foundry configuration is missing."""


def analyze_operational_exception(
    context: OperationalExceptionContext,
) -> CopilotRunResult:
    """Analyze one operational exception using structured output."""

    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    model = os.getenv("FOUNDRY_MODEL_NAME", DEFAULT_MODEL).strip()

    if not endpoint:
        raise CopilotConfigurationError(
            "FOUNDRY_PROJECT_ENDPOINT is not configured."
        )

    credential = DefaultAzureCredential()

    project = AIProjectClient(
        endpoint=endpoint,
        credential=credential,
    )

    client = project.get_openai_client()

    try:
        response = client.responses.parse(
            model=model,
            instructions=ACTIVE_PROMPT,
            input=context.model_dump_json(indent=2),
            text_format=CopilotAnalysis,
        )

        analysis = response.output_parsed

        if analysis is None:
            raise RuntimeError(
                "GPT-5-mini returned no structured Copilot analysis."
            )

        analysis = sanitize_human_facing_analysis(analysis)

        return CopilotRunResult(
            prompt_version=PROMPT_VERSION,
            model=model,
            analysis=analysis,
        )

    finally:
        client.close()
        project.close()
        credential.close()
