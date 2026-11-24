"""Tests for M2: Extraction."""

import json
from unittest.mock import patch

from crm_copilot.extract import _verify_evidence_quotes, extract_insights
from crm_copilot.models import CallInsights, MeddpiccField

SAMPLE_TRANSCRIPT = """
John: Thanks for taking the call, Sarah. So Acme Corp is looking to replace your legacy CRM?
Sarah: Yes, we've been using a homegrown tool for 5 years and it's becoming a bottleneck.
John: What's the main pain point?
Sarah: Our reps waste about 10 hours a week on manual data entry. That's the big one.
John: Got it. And who's driving this evaluation?
Sarah: I'm leading it, but our VP of Sales, Mike, makes the final call.
John: Any competitors you're looking at?
Sarah: We're also evaluating HubSpot. But we need something that integrates with Salesforce.
John: What's your timeline?
Sarah: We want to decide by end of Q1. Budget is approved up to $50k/year.
John: Great, let's schedule a technical demo for next Tuesday.
Sarah: Tuesday works. January 16th at 2pm.
"""

EXPECTED_INSIGHTS_JSON = {
    "company_name": "Acme Corp",
    "contact_names": ["Sarah", "John", "Mike"],
    "summary": (
        "Discovery call with Acme Corp about replacing legacy CRM. "
        "Main pain is 10 hrs/week manual entry. Evaluating HubSpot, "
        "needs Salesforce integration. Decision by end of Q1, budget $50k."
    ),
    "meddpicc": {
        "metrics": {
            "value": "Reduce manual entry by 10 hours/week per rep",
            "evidence_quote": "Our reps waste about 10 hours a week on manual data entry",
            "confidence": "high",
        },
        "economic_buyer": {
            "value": "Mike - VP of Sales",
            "evidence_quote": "our VP of Sales, Mike, makes the final call",
            "confidence": "high",
        },
        "decision_criteria": {
            "value": "Salesforce integration required",
            "evidence_quote": "we need something that integrates with Salesforce",
            "confidence": "high",
        },
        "decision_process": {
            "value": "Technical demo then decision by end of Q1",
            "evidence_quote": "We want to decide by end of Q1",
            "confidence": "medium",
        },
        "paper_process": {
            "value": None,
            "evidence_quote": None,
            "confidence": "low",
        },
        "identify_pain": {
            "value": "Manual data entry wasting 10 hrs/week per rep",
            "evidence_quote": "Our reps waste about 10 hours a week on manual data entry",
            "confidence": "high",
        },
        "champion": {
            "value": "Sarah - leading evaluation",
            "evidence_quote": "I'm leading it",
            "confidence": "high",
        },
        "competition": {
            "value": "HubSpot",
            "evidence_quote": "We're also evaluating HubSpot",
            "confidence": "high",
        },
    },
    "objections": [],
    "next_step": "Technical demo",
    "next_step_date": "2024-01-16",
    "budget_signal": "Budget approved up to $50k/year",
    "timeline_signal": "Decision by end of Q1",
}


class TestVerifyEvidenceQuotes:
    """Test anti-hallucination guard."""

    def test_valid_quote_kept(self) -> None:
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                "metrics": MeddpiccField(
                    value="Test value",
                    evidence_quote="waste about 10 hours",
                    confidence="high",
                ),
                "economic_buyer": MeddpiccField(),
                "decision_criteria": MeddpiccField(),
                "decision_process": MeddpiccField(),
                "paper_process": MeddpiccField(),
                "identify_pain": MeddpiccField(),
                "champion": MeddpiccField(),
                "competition": MeddpiccField(),
            },
        )
        result = _verify_evidence_quotes(insights, SAMPLE_TRANSCRIPT)
        assert result.meddpicc["metrics"].value == "Test value"
        assert result.meddpicc["metrics"].evidence_quote == "waste about 10 hours"
        assert result.meddpicc["metrics"].confidence == "high"

    def test_invalid_quote_nulled(self) -> None:
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                "metrics": MeddpiccField(
                    value="Test value",
                    evidence_quote="this quote does not exist in transcript",
                    confidence="high",
                ),
                "economic_buyer": MeddpiccField(),
                "decision_criteria": MeddpiccField(),
                "decision_process": MeddpiccField(),
                "paper_process": MeddpiccField(),
                "identify_pain": MeddpiccField(),
                "champion": MeddpiccField(),
                "competition": MeddpiccField(),
            },
        )
        result = _verify_evidence_quotes(insights, SAMPLE_TRANSCRIPT)
        assert result.meddpicc["metrics"].value is None
        assert result.meddpicc["metrics"].evidence_quote is None
        assert result.meddpicc["metrics"].confidence == "low"

    def test_null_quote_unchanged(self) -> None:
        insights = CallInsights(
            company_name="Test",
            meddpicc={
                "metrics": MeddpiccField(value=None, evidence_quote=None, confidence="low"),
                "economic_buyer": MeddpiccField(),
                "decision_criteria": MeddpiccField(),
                "decision_process": MeddpiccField(),
                "paper_process": MeddpiccField(),
                "identify_pain": MeddpiccField(),
                "champion": MeddpiccField(),
                "competition": MeddpiccField(),
            },
        )
        result = _verify_evidence_quotes(insights, SAMPLE_TRANSCRIPT)
        assert result.meddpicc["metrics"].value is None
        assert result.meddpicc["metrics"].evidence_quote is None
        assert result.meddpicc["metrics"].confidence == "low"


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


def test_extract_insights_calls_llm_and_verifies() -> None:
    """Test extract_insights calls LLM and runs verification."""
    fake_response = json.dumps(EXPECTED_INSIGHTS_JSON)

    with patch("crm_copilot.extract.complete_json") as mock_complete:
        mock_complete.return_value = CallInsights.model_validate_json(fake_response)

        result = extract_insights(SAMPLE_TRANSCRIPT)

        # Verify LLM was called
        mock_complete.assert_called_once()
        call_args = mock_complete.call_args
        assert call_args.kwargs["schema"] is CallInsights
        assert SAMPLE_TRANSCRIPT in call_args.kwargs["user"]

        # Verify result matches expected
        assert result.company_name == "Acme Corp"
        assert "Sarah" in result.contact_names
        assert result.meddpicc["metrics"].value is not None
        assert result.meddpicc["metrics"].evidence_quote in SAMPLE_TRANSCRIPT


def test_extract_insights_hallucinated_quote_removed() -> None:
    """Test that hallucinated quotes are removed by verification."""
    # Response with a quote NOT in the transcript
    bad_insights = EXPECTED_INSIGHTS_JSON.copy()
    bad_insights["meddpicc"]["metrics"]["evidence_quote"] = "this is not in the transcript at all"
    fake_response = json.dumps(bad_insights)

    with patch("crm_copilot.extract.complete_json") as mock_complete:
        mock_complete.return_value = CallInsights.model_validate_json(fake_response)

        result = extract_insights(SAMPLE_TRANSCRIPT)

        # The bad quote should be nulled
        assert result.meddpicc["metrics"].value is None
        assert result.meddpicc["metrics"].evidence_quote is None
        assert result.meddpicc["metrics"].confidence == "low"