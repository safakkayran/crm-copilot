"""Extraction module: transcript -> CallInsights via LLM."""

from __future__ import annotations

from pathlib import Path

from crm_copilot.llm import complete_json
from crm_copilot.models import CallInsights

# Load extraction prompt
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "extract.md"
EXTRACT_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


def _verify_evidence_quotes(insights: CallInsights, transcript: str) -> CallInsights:
    """
    Anti-hallucination guard: verify every evidence_quote is a substring of transcript.
    If not found, nullify the field.
    """
    # Check MEDDPICC fields
    for _field_name, field in insights.meddpicc.items():
        if field.evidence_quote and field.evidence_quote not in transcript:
            # Quote not found in transcript - nullify
            field.value = None
            field.evidence_quote = None
            field.confidence = "low"

    # Check other fields that might have evidence (objections, next_step, etc.)
    # These don't have evidence_quote in the model, so no verification needed

    return insights


def extract_insights(transcript: str) -> CallInsights:
    """
    Extract structured insights from a sales call transcript.

    Args:
        transcript: Raw call transcript text

    Returns:
        CallInsights with extracted and verified data
    """
    user_prompt = f"TRANSCRIPT:\n{transcript}\n\nExtract insights as JSON."

    insights = complete_json(
        system=EXTRACT_PROMPT,
        user=user_prompt,
        schema=CallInsights,
    )

    # Anti-hallucination: verify all evidence quotes exist in transcript
    return _verify_evidence_quotes(insights, transcript)