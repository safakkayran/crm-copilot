"""Follow-up email drafting using LLM."""

from __future__ import annotations  # noqa: I001

from crm_copilot.llm import complete_json
from crm_copilot.models import CallInsights, EmailDraft


FOLLOWUP_PROMPT = """You are a sales professional writing a follow-up email after a discovery call.

Write a short, plain-text follow-up email that:
- References the specific next step discussed
- Is professional but concise (3-5 sentences max)
- Does NOT use em dashes (—)
- Does NOT use markdown formatting
- Uses the prospect's company name and contact name if available

Return JSON with "subject" and "body" fields."""


def draft_followup(insights: CallInsights) -> EmailDraft:
    """
    Draft a follow-up email using LLM.

    Args:
        insights: Extracted call insights

    Returns:
        EmailDraft with subject and body
    """
    # Build context for LLM
    contact = insights.contact_names[0] if insights.contact_names else "there"
    company = insights.company_name
    next_step = insights.next_step or "our next conversation"
    next_step_date = f" on {insights.next_step_date}" if insights.next_step_date else ""

    user_prompt = f"""
Company: {company}
Contact: {contact}
Next step: {next_step}{next_step_date}
Key pain point: {insights.meddpicc["identify_pain"].value or "Not identified"}
Budget signal: {insights.budget_signal or "Not discussed"}

Write a follow-up email.
"""

    email = complete_json(
        system=FOLLOWUP_PROMPT,
        user=user_prompt,
        schema=EmailDraft,
    )

    # Post-process: ensure no em dashes
    email.body = email.body.replace("—", "-").replace("–", "-")
    email.subject = email.subject.replace("—", "-").replace("–", "-")

    return email