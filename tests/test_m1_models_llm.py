"""Tests for M1: Models + LLM wrapper."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from crm_copilot.config import Settings, settings
from crm_copilot.llm import CachedLLMClient, complete_json, get_llm_client
from crm_copilot.models import (
    CallInsights,
    EmailDraft,
    MeddpiccField,
    StageSuggestion,
    TaskDraft,
    UpdatePlan,
)


class TestModels:
    """Test Pydantic models."""

    def test_meddpicc_field_defaults(self) -> None:
        field = MeddpiccField()
        assert field.value is None
        assert field.evidence_quote is None
        assert field.confidence == "low"

    def test_meddpicc_field_with_values(self) -> None:
        field = MeddpiccField(
            value="Champion found",
            evidence_quote="John is the champion",
            confidence="high",
        )
        assert field.value == "Champion found"
        assert field.evidence_quote == "John is the champion"
        assert field.confidence == "high"

    def test_call_insights_defaults(self) -> None:
        insights = CallInsights(company_name="Acme Corp")
        assert insights.company_name == "Acme Corp"
        assert insights.contact_names == []
        assert insights.summary == ""
        expected_meddpicc_keys = 8
        assert len(insights.meddpicc) == expected_meddpicc_keys
        assert all(isinstance(v, MeddpiccField) for v in insights.meddpicc.values())

    def test_stage_suggestion(self) -> None:
        stage = StageSuggestion(stage="qualified", reason="Pain and champion identified")
        assert stage.stage == "qualified"
        assert stage.reason == "Pain and champion identified"

    def test_task_draft(self) -> None:
        task = TaskDraft(title="Follow up", body="Send proposal", due_at="2024-01-15T10:00:00")
        assert task.title == "Follow up"
        assert task.due_at == "2024-01-15T10:00:00"

    def test_email_draft(self) -> None:
        email = EmailDraft(subject="Re: Meeting", body="Thanks for the call")
        assert email.subject == "Re: Meeting"
        assert email.body == "Thanks for the call"

    def test_update_plan(self) -> None:
        plan = UpdatePlan(
            company_name="Acme Corp",
            opportunity_fields={"stage": "qualified"},
            note_markdown="## Notes\nGood call",
            tasks=[TaskDraft(title="Follow up")],
            followup_email=EmailDraft(subject="Thanks", body="Great call"),
            missing_fields=["metrics", "paper_process"],
            stage=StageSuggestion(stage="qualified", reason="Pain + champion"),
        )
        assert plan.company_name == "Acme Corp"
        expected_task_count = 1
        assert len(plan.tasks) == expected_task_count
        expected_missing_count = 2
        assert len(plan.missing_fields) == expected_missing_count


class TestConfig:
    """Test configuration."""

    def test_settings_load(self) -> None:
        assert settings.LLM_BASE_URL == "http://127.0.0.1:4000"
        assert settings.LLM_MODEL == "nim-laguna"
        assert settings.TWENTY_BASE_URL == "http://localhost:3000"

    def test_settings_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("LLM_MODEL", "custom-model")
        monkeypatch.setenv("TWENTY_API_KEY", "test-key")
        new_settings = Settings()
        assert new_settings.LLM_MODEL == "custom-model"
        assert new_settings.TWENTY_API_KEY == "test-key"


class FakeOpenAIResponse:
    """Fake OpenAI response for testing."""

    def __init__(self, content: str) -> None:
        self.choices = [MagicMock(message=MagicMock(content=content))]


class FakeOpenAIClient:
    """Fake OpenAI client for testing."""

    def __init__(self, responses: list[str] | str) -> None:
        if isinstance(responses, str):
            responses = [responses]
        self.responses = responses
        self.call_count = 0
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = self._create

    def _create(self, **_kwargs) -> FakeOpenAIResponse:
        if self.call_count >= len(self.responses):
            raise RuntimeError("No more fake responses")
        response = FakeOpenAIResponse(self.responses[self.call_count])
        self.call_count += 1
        return response


def test_llm_cache_hit(tmp_path: Path) -> None:
    """Test that LLM cache works on second call."""
    # Create a client with a fake OpenAI client
    client = CachedLLMClient()
    client.cache_dir = tmp_path / "llm_cache"
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    # First response
    fake_response = json.dumps({
        "company_name": "Test Corp",
        "contact_names": [],
        "summary": "Test call",
        "meddpicc": {
            "metrics": {"value": None, "evidence_quote": None, "confidence": "low"},
            "economic_buyer": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_criteria": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "paper_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "identify_pain": {"value": None, "evidence_quote": None, "confidence": "low"},
            "champion": {"value": None, "evidence_quote": None, "confidence": "low"},
            "competition": {"value": None, "evidence_quote": None, "confidence": "low"},
        },
        "objections": [],
        "next_step": None,
        "next_step_date": None,
        "budget_signal": None,
        "timeline_signal": None,
    })

    # Patch the OpenAI client
    with patch.object(client, "client", FakeOpenAIClient(fake_response)):
        # First call - should hit API
        result1 = client.complete_json("system", "user", CallInsights)
        assert result1.company_name == "Test Corp"
        fake_client = client.client
        assert fake_client.call_count == 1

        # Second call - should hit cache
        result2 = client.complete_json("system", "user", CallInsights)
        assert result2.company_name == "Test Corp"
        assert fake_client.call_count == 1  # No additional API call


def test_llm_invalid_json_then_valid(tmp_path: Path) -> None:
    """Test retry on invalid JSON."""
    client = CachedLLMClient()
    client.cache_dir = tmp_path / "llm_cache"
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    # First response: invalid JSON, second: valid
    invalid_json = '{"company_name": "Test", "contact_names": []'  # Missing closing brace
    valid_json = json.dumps({
        "company_name": "Test Corp",
        "contact_names": [],
        "summary": "Test call",
        "meddpicc": {
            "metrics": {"value": None, "evidence_quote": None, "confidence": "low"},
            "economic_buyer": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_criteria": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "paper_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "identify_pain": {"value": None, "evidence_quote": None, "confidence": "low"},
            "champion": {"value": None, "evidence_quote": None, "confidence": "low"},
            "competition": {"value": None, "evidence_quote": None, "confidence": "low"},
        },
        "objections": [],
        "next_step": None,
        "next_step_date": None,
        "budget_signal": None,
        "timeline_signal": None,
    })

    fake_client = FakeOpenAIClient([invalid_json, valid_json])
    with patch.object(client, "client", fake_client):
        result = client.complete_json("system", "user", CallInsights, max_retries=1)
        assert result.company_name == "Test Corp"
        expected_call_count = 2
        assert fake_client.call_count == expected_call_count


def test_llm_429_retry(tmp_path: Path) -> None:
    """Test retry on 429 rate limit."""
    client = CachedLLMClient()
    client.cache_dir = tmp_path / "llm_cache"
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    valid_json = json.dumps({
        "company_name": "Test Corp",
        "contact_names": [],
        "summary": "Test call",
        "meddpicc": {
            "metrics": {"value": None, "evidence_quote": None, "confidence": "low"},
            "economic_buyer": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_criteria": {"value": None, "evidence_quote": None, "confidence": "low"},
            "decision_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "paper_process": {"value": None, "evidence_quote": None, "confidence": "low"},
            "identify_pain": {"value": None, "evidence_quote": None, "confidence": "low"},
            "champion": {"value": None, "evidence_quote": None, "confidence": "low"},
            "competition": {"value": None, "evidence_quote": None, "confidence": "low"},
        },
        "objections": [],
        "next_step": None,
        "next_step_date": None,
        "budget_signal": None,
        "timeline_signal": None,
    })

    # First call raises 429, second succeeds
    class RateLimitClient:
        def __init__(self) -> None:
            self.call_count = 0

        def chat_completions_create(self, **_kwargs) -> FakeOpenAIResponse:
            self.call_count += 1
            if self.call_count == 1:
                raise Exception("429 Rate limit exceeded")
            return FakeOpenAIResponse(valid_json)

    rate_client = RateLimitClient()
    client.client = MagicMock()
    client.client.chat.completions.create = rate_client.chat_completions_create

    result = client.complete_json("system", "user", CallInsights, max_retries=2)
    assert result.company_name == "Test Corp"
    expected_retry_count = 2
    assert rate_client.call_count == expected_retry_count


def test_complete_json_convenience_function(tmp_path: Path) -> None:
    """Test the convenience function works."""
    client = get_llm_client()
    client.cache_dir = tmp_path / "llm_cache"
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    valid_json = json.dumps({
        "stage": "qualified",
        "reason": "Pain and champion found",
    })

    with patch.object(client, "client", FakeOpenAIClient(valid_json)):
        result = complete_json("system", "user", StageSuggestion)
        assert result.stage == "qualified"
        assert result.reason == "Pain and champion found"