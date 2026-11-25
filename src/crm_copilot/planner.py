"""Planner module: CallInsights -> UpdatePlan (pure Python, deterministic)."""

from __future__ import annotations

import json

from crm_copilot.models import CallInsights, StageSuggestion, TaskDraft, UpdatePlan

# Stage mapping from our internal stages to Twenty's stage values
# Loaded from ANSWERS.md / settings
DEFAULT_STAGE_MAPPING = {
    "discovery": "SCREENING",
    "qualified": "MEETING",
    "evaluation": "PROPOSAL",
    "negotiation": "PROPOSAL",
}


def _determine_stage(insights: CallInsights) -> StageSuggestion:
    """
    Determine deal stage based on MEDDPICC fields.
    Rules (deterministic, documented in README):
    - no identified pain -> discovery
    - pain + champion -> qualified
    - pain + champion + economic_buyer + decision_process -> evaluation
    - all of the above + paper_process -> negotiation
    """
    pain = insights.meddpicc["identify_pain"].value is not None
    champion = insights.meddpicc["champion"].value is not None
    economic_buyer = insights.meddpicc["economic_buyer"].value is not None
    decision_process = insights.meddpicc["decision_process"].value is not None
    paper_process = insights.meddpicc["paper_process"].value is not None

    if not pain:
        return StageSuggestion(
            stage="discovery",
            reason="No identified pain in transcript",
        )
    if pain and champion and not (economic_buyer and decision_process):
        return StageSuggestion(
            stage="qualified",
            reason="Pain and champion identified, but missing economic buyer or decision process",
        )
    if pain and champion and economic_buyer and decision_process and not paper_process:
        return StageSuggestion(
            stage="evaluation",
            reason="Pain, champion, economic buyer, and decision process identified",
        )
    if pain and champion and economic_buyer and decision_process and paper_process:
        return StageSuggestion(
            stage="negotiation",
            reason="All MEDDPICC components including paper process identified",
        )

    # Fallback (should not reach here with current logic)
    return StageSuggestion(stage="discovery", reason="Default fallback")


def _build_missing_fields(insights: CallInsights) -> list[str]:
    """Build list of missing MEDDPICC fields as questions for next call."""
    questions = {
        "metrics": "What metrics or ROI targets does the prospect have?",
        "economic_buyer": "Who is the economic buyer / final decision maker?",
        "decision_criteria": "What are the technical/functional evaluation criteria?",
        "decision_process": "What is the decision process and timeline?",
        "paper_process": "What is the procurement/legal/security review process?",
        "identify_pain": "What specific business pain is driving this evaluation?",
        "champion": "Who is the internal champion advocating for this solution?",
        "competition": "What competitors or alternatives are being evaluated?",
    }
    missing = []
    for key, question in questions.items():
        if insights.meddpicc[key].value is None:
            missing.append(question)
    return missing


def _build_opportunity_fields(
    insights: CallInsights,
    stage_suggestion: StageSuggestion,
) -> dict[str, object]:
    """Build opportunity fields dict for CRM update."""
    # Map our internal stage to Twenty's stage value
    twenty_stage = DEFAULT_STAGE_MAPPING.get(stage_suggestion.stage, "SCREENING")

    fields: dict[str, object] = {
        "name": f"{insights.company_name} - {stage_suggestion.stage.capitalize()}",
        "stage": twenty_stage,
    }

    # Only set amount if budget was mentioned
    if insights.budget_signal:
        # Try to extract a number from budget_signal (simplified)
        # In practice, this would be more sophisticated
        fields["amount"] = {"amountMicros": 50000000000, "currencyCode": "USD"}  # $50k placeholder

    if insights.next_step_date:
        fields["closeDate"] = insights.next_step_date

    # MEDDPICC custom field (Option A) - compact JSON
    meddpicc_json = {}
    for k, v in insights.meddpicc.items():
        meddpicc_json[k] = {"value": v.value, "confidence": v.confidence}
    fields["meddpicc"] = json_dumps_compact(meddpicc_json)

    return fields


def json_dumps_compact(obj: dict) -> str:
    """Compact JSON without whitespace."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _build_note_markdown(insights: CallInsights) -> str:
    """Build markdown note body with MEDDPICC table."""
    lines = [
        f"# Call Notes - {insights.company_name}",
        "",
        f"**Summary**: {insights.summary or 'No summary extracted'}",
        "",
        "## MEDDPICC",
        "",
        "| Field | Value | Confidence | Evidence |",
        "|-------|-------|------------|----------|",
    ]

    for field_name, field in insights.meddpicc.items():
        value = field.value or "—"
        confidence = field.confidence
        evidence = field.evidence_quote or "—"
        lines.append(f"| {field_name} | {value} | {confidence} | {evidence} |")

    lines.extend([
        "",
        "## Objections",
        "",
    ])

    if insights.objections:
        for obj in insights.objections:
            lines.append(f"- {obj}")
    else:
        lines.append("None recorded")

    lines.extend([
        "",
        "## Next Steps",
        "",
    ])

    if insights.next_step:
        lines.append(f"- **Action**: {insights.next_step}")
        if insights.next_step_date:
            lines.append(f"  **Date**: {insights.next_step_date}")
    else:
        lines.append("No clear next step identified")

    if insights.budget_signal:
        lines.append(f"- **Budget**: {insights.budget_signal}")
    if insights.timeline_signal:
        lines.append(f"- **Timeline**: {insights.timeline_signal}")

    return "\n".join(lines)


def _build_tasks(insights: CallInsights) -> list[TaskDraft]:
    """Build task drafts from next steps."""
    tasks = []
    if insights.next_step:
        task = TaskDraft(
            title=f"Follow up: {insights.next_step[:50]}",
            body=insights.next_step,
            due_at=insights.next_step_date,
        )
        tasks.append(task)
    return tasks


def plan_updates(insights: CallInsights) -> UpdatePlan:
    """
    Create a complete CRM update plan from call insights.
    Pure Python - no LLM calls except followup email.
    """
    # Determine stage
    stage_suggestion = _determine_stage(insights)

    # Build components
    opportunity_fields = _build_opportunity_fields(insights, stage_suggestion)
    note_markdown = _build_note_markdown(insights)
    tasks = _build_tasks(insights)
    missing_fields = _build_missing_fields(insights)

    # Draft follow-up email (uses LLM) - import locally to avoid circular import
    from crm_copilot.followup import draft_followup  # noqa: PLC0415
    followup_email = draft_followup(insights)

    return UpdatePlan(
        company_name=insights.company_name,
        opportunity_fields=opportunity_fields,
        note_markdown=note_markdown,
        tasks=tasks,
        followup_email=followup_email,
        missing_fields=missing_fields,
        stage=stage_suggestion,
    )