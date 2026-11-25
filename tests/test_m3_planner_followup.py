"""Tests for M3: Planner + follow-up."""

import json
from unittest.mock import patch

from crm_copilot.followup import draft_followup
from crm_copilot.models import (
    CallInsights,
    EmailDraft,
    MeddpiccField,
    StageSuggestion,
    UpdatePlan,
)
from crm_copilot.planner import (
    _build_missing_fields,
    _build_note_markdown,
    _build_opportunity_fields,
    _build_tasks,
    _determine_stage,
    json_dumps_compact,
    plan_updates,
)

SAMPLE_INSIGHTS = CallInsights(
    company_name="Acme Corp",
    contact_names=["Sarah"],
    summary="Discovery call about CRM replacement",
    meddpicc={
        "metrics": MeddpiccField(
            value="Reduce manual entry 10 hrs/week",
            evidence_quote="...",
            confidence="high",
        ),
        "economic_buyer": MeddpiccField(
            value="Mike - VP Sales",
            evidence_quote="...",
            confidence="high",
        ),
        "decision_criteria": MeddpiccField(
            value="Salesforce integration",
            evidence_quote="...",
            confidence="high",
        ),
        "decision_process": MeddpiccField(
            value="Technical eval then procurement",
            evidence_quote="...",
            confidence="medium",
        ),
        "paper_process": MeddpiccField(
            value=None,
            evidence_quote=None,
            confidence="low",
        ),
        "identify_pain": MeddpiccField(
            value="Manual data entry 10 hrs/week",
            evidence_quote="...",
            confidence="high",
        ),
        "champion": MeddpiccField(
            value="Sarah - Sales Ops",
            evidence_quote="...",
            confidence="high",
        ),
        "competition": MeddpiccField(
            value="HubSpot",
            evidence_quote="...",
            confidence="medium",
        ),
    },
    objections=["Price", "Timeline"],
    next_step="Technical demo",
    next_step_date="2024-01-16",
    budget_signal="$50k/year approved",
    timeline_signal="Decision by end of Q1",
)

INSIGHTS_NO_PAIN = CallInsights(
    company_name="Test Corp",
    contact_names=[],
    summary="Initial contact",
    meddpicc={
        "metrics": MeddpiccField(),
        "economic_buyer": MeddpiccField(),
        "decision_criteria": MeddpiccField(),
        "decision_process": MeddpiccField(),
        "paper_process": MeddpiccField(),
        "identify_pain": MeddpiccField(),  # No pain
        "champion": MeddpiccField(),
        "competition": MeddpiccField(),
    },
)

INSIGHTS_PAIN_CHAMPION = CallInsights(
    company_name="Test Corp",
    contact_names=[],
    summary="Initial contact",
    meddpicc={
        "metrics": MeddpiccField(),
        "economic_buyer": MeddpiccField(),
        "decision_criteria": MeddpiccField(),
        "decision_process": MeddpiccField(),
        "paper_process": MeddpiccField(),
        "identify_pain": MeddpiccField(
            value="Pain exists",
            evidence_quote="...",
            confidence="high",
        ),
        "champion": MeddpiccField(
            value="Champion",
            evidence_quote="...",
            confidence="high",
        ),
        "competition": MeddpiccField(),
    },
)

INSIGHTS_FULL = CallInsights(
    company_name="Test Corp",
    contact_names=[],
    summary="Full MEDDPICC",
    meddpicc={
        "metrics": MeddpiccField(
            value="Metrics",
            evidence_quote="...",
            confidence="high",
        ),
        "economic_buyer": MeddpiccField(
            value="Buyer",
            evidence_quote="...",
            confidence="high",
        ),
        "decision_criteria": MeddpiccField(
            value="Criteria",
            evidence_quote="...",
            confidence="high",
        ),
        "decision_process": MeddpiccField(
            value="Process",
            evidence_quote="...",
            confidence="high",
        ),
        "paper_process": MeddpiccField(
            value="Paper",
            evidence_quote="...",
            confidence="high",
        ),
        "identify_pain": MeddpiccField(
            value="Pain",
            evidence_quote="...",
            confidence="high",
        ),
        "champion": MeddpiccField(
            value="Champion",
            evidence_quote="...",
            confidence="high",
        ),
        "competition": MeddpiccField(
            value="Competitor",
            evidence_quote="...",
            confidence="high",
        ),
    },
)


class TestDetermineStage:
    """Test stage determination rules."""

    def test_no_pain_discovery(self) -> None:
        stage = _determine_stage(INSIGHTS_NO_PAIN)
        assert stage.stage == "discovery"
        assert "No identified pain" in stage.reason

    def test_pain_champion_qualified(self) -> None:
        stage = _determine_stage(INSIGHTS_PAIN_CHAMPION)
        assert stage.stage == "qualified"
        assert "Pain and champion" in stage.reason

    def test_pain_champion_buyer_process_evaluation(self) -> None:
        # Missing paper_process -> evaluation
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                "metrics": MeddpiccField(),
                "economic_buyer": MeddpiccField(
                    value="Buyer",
                    evidence_quote="...",
                    confidence="high",
                ),
                "decision_criteria": MeddpiccField(),
                "decision_process": MeddpiccField(
                    value="Process",
                    evidence_quote="...",
                    confidence="high",
                ),
                "paper_process": MeddpiccField(),  # Missing
                "identify_pain": MeddpiccField(
                    value="Pain",
                    evidence_quote="...",
                    confidence="high",
                ),
                "champion": MeddpiccField(
                    value="Champion",
                    evidence_quote="...",
                    confidence="high",
                ),
                "competition": MeddpiccField(),
            },
        )
        stage = _determine_stage(insights)
        assert stage.stage == "evaluation"

    def test_full_meddpicc_negotiation(self) -> None:
        stage = _determine_stage(INSIGHTS_FULL)
        assert stage.stage == "negotiation"
        assert "All MEDDPICC" in stage.reason


class TestBuildMissingFields:
    """Test missing fields generation."""

    def test_all_missing(self) -> None:
        missing = _build_missing_fields(INSIGHTS_NO_PAIN)
        expected_count = 8
        assert len(missing) == expected_count  # All 8 MEDDPICC fields

    def test_some_missing(self) -> None:
        missing = _build_missing_fields(SAMPLE_INSIGHTS)
        # paper_process is None in SAMPLE_INSIGHTS
        assert len(missing) == 1
        assert "procurement" in missing[0].lower()


class TestBuildOpportunityFields:
    """Test opportunity fields building."""

    def test_basic_fields(self) -> None:
        stage = StageSuggestion(stage="qualified", reason="Test")
        fields = _build_opportunity_fields(SAMPLE_INSIGHTS, stage)

        assert fields["name"] == "Acme Corp - Qualified"
        assert fields["stage"] == "MEETING"  # qualified -> MEETING
        assert "amount" in fields  # budget_signal present
        assert "closeDate" in fields  # next_step_date present
        assert "meddpicc" in fields

    def test_no_budget_no_amount(self) -> None:
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                k: MeddpiccField()
                for k in [
                    "metrics",
                    "economic_buyer",
                    "decision_criteria",
                    "decision_process",
                    "paper_process",
                    "identify_pain",
                    "champion",
                    "competition",
                ]
            },
            budget_signal=None,
            next_step_date=None,
        )
        stage = StageSuggestion(stage="discovery", reason="Test")
        fields = _build_opportunity_fields(insights, stage)

        assert "amount" not in fields
        assert "closeDate" not in fields


class TestJsonDumpsCompact:
    """Test compact JSON serialization."""

    def test_compact(self) -> None:
        result = json_dumps_compact({"a": 1, "b": "test"})
        assert result == '{"a":1,"b":"test"}'


class TestBuildNoteMarkdown:
    """Test note markdown generation."""

    def test_contains_sections(self) -> None:
        markdown = _build_note_markdown(SAMPLE_INSIGHTS)

        assert "# Call Notes - Acme Corp" in markdown
        assert "## MEDDPICC" in markdown
        assert "## Objections" in markdown
        assert "## Next Steps" in markdown
        assert "Technical demo" in markdown
        assert "2024-01-16" in markdown
        assert "$50k/year" in markdown


class TestBuildTasks:
    """Test task generation."""

    def test_with_next_step(self) -> None:
        tasks = _build_tasks(SAMPLE_INSIGHTS)
        assert len(tasks) == 1
        assert tasks[0].title.startswith("Follow up:")
        assert tasks[0].due_at == "2024-01-16"

    def test_no_next_step(self) -> None:
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                k: MeddpiccField()
                for k in [
                    "metrics",
                    "economic_buyer",
                    "decision_criteria",
                    "decision_process",
                    "paper_process",
                    "identify_pain",
                    "champion",
                    "competition",
                ]
            },
            next_step=None,
        )
        tasks = _build_tasks(insights)
        assert len(tasks) == 0


class FakeOpenAIResponse:
    def __init__(self, content: str) -> None:
        msg = type("msg", (object,), {"content": content})()
        choice = type("obj", (object,), {"message": msg})()
        self.choices = [choice]


class FakeOpenAIClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.call_count = 0
        self.chat = type("chat", (object,), {})()
        self.chat.completions = type("completions", (object,), {})()
        self.chat.completions.create = self._create

    def _create(self, **_kwargs) -> FakeOpenAIResponse:
        self.call_count += 1
        return FakeOpenAIResponse(self.response)


def test_draft_followup_no_em_dash() -> None:
    """Test followup email has no em dashes."""
    fake_response = json.dumps({
        "subject": "Follow up",
        "body": "Thanks for the call. Next step is demo on Tuesday.",
    })

    with patch("crm_copilot.followup.complete_json") as mock_complete:
        mock_complete.return_value = EmailDraft.model_validate_json(fake_response)

        email = draft_followup(SAMPLE_INSIGHTS)

        assert "—" not in email.subject
        assert "—" not in email.body
        assert "–" not in email.subject
        assert "–" not in email.body


def test_plan_updates_integration() -> None:
    """Test full plan_updates integration."""
    fake_email = json.dumps({
        "subject": "Follow up",
        "body": "Thanks for the call. Next step is demo.",
    })

    with patch("crm_copilot.followup.complete_json") as mock_complete:
        mock_complete.return_value = EmailDraft.model_validate_json(fake_email)

        plan = plan_updates(SAMPLE_INSIGHTS)

        assert isinstance(plan, UpdatePlan)
        assert plan.company_name == "Acme Corp"
        assert plan.stage.stage in ("discovery", "qualified", "evaluation", "negotiation")
        assert plan.note_markdown != ""
        assert len(plan.tasks) >= 0
        assert plan.followup_email.subject == "Follow up"
        assert isinstance(plan.missing_fields, list)