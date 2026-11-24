"""Pydantic models for crm-copilot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MeddpiccField(BaseModel):
    """A single MEDDPICC field with value, evidence, and confidence."""

    value: str | None = None
    evidence_quote: str | None = None
    confidence: Literal["low", "medium", "high"] = "low"


class CallInsights(BaseModel):
    """Extracted insights from a sales call transcript."""

    company_name: str
    contact_names: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="Max ~80 words")
    meddpicc: dict[str, MeddpiccField] = Field(
        default_factory=lambda: {
            "metrics": MeddpiccField(),
            "economic_buyer": MeddpiccField(),
            "decision_criteria": MeddpiccField(),
            "decision_process": MeddpiccField(),
            "paper_process": MeddpiccField(),
            "identify_pain": MeddpiccField(),
            "champion": MeddpiccField(),
            "competition": MeddpiccField(),
        }
    )
    objections: list[str] = Field(default_factory=list)
    next_step: str | None = None
    next_step_date: str | None = None  # ISO date if stated
    budget_signal: str | None = None
    timeline_signal: str | None = None


class StageSuggestion(BaseModel):
    """Suggested deal stage with reasoning."""

    stage: str
    reason: str


class TaskDraft(BaseModel):
    """Draft task to create in CRM."""

    title: str
    body: str = ""
    due_at: str | None = None  # ISO datetime


class EmailDraft(BaseModel):
    """Draft follow-up email."""

    subject: str
    body: str


class UpdatePlan(BaseModel):
    """Complete plan for CRM updates after a call."""

    company_name: str
    opportunity_fields: dict[str, Any] = Field(default_factory=dict)
    note_markdown: str = ""
    tasks: list[TaskDraft] = Field(default_factory=list)
    followup_email: EmailDraft = Field(
        default_factory=lambda: EmailDraft(subject="", body="")
    )
    missing_fields: list[str] = Field(default_factory=list)
    stage: StageSuggestion = Field(
        default_factory=lambda: StageSuggestion(stage="discovery", reason="")
    )


class ApplyResult(BaseModel):
    """Result of applying a plan to CRM."""

    company_id: str | None = None
    opportunity_id: str | None = None
    note_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    updated: bool = False