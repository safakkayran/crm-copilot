"""Tests for M4: Fake adapter + apply + CLI."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from crm_copilot.apply import apply_plan
from crm_copilot.cli import app
from crm_copilot.crm.fake import FakeAdapter
from crm_copilot.models import (
    CallInsights,
    EmailDraft,
    MeddpiccField,
    StageSuggestion,
    TaskDraft,
    UpdatePlan,
)

runner = CliRunner()


class TestFakeAdapter:
    """Test FakeAdapter implementation."""

    def test_find_company_not_exists(self) -> None:
        adapter = FakeAdapter()
        assert adapter.find_company("NonExistent") is None

    def test_upsert_company(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp", "test.com")
        assert company_id is not None
        assert adapter.find_company("Test Corp") == company_id

    def test_upsert_company_idempotent(self) -> None:
        adapter = FakeAdapter()
        id1 = adapter.upsert_company("Test Corp")
        id2 = adapter.upsert_company("Test Corp")
        assert id1 == id2

    def test_find_open_opportunity_none(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp")
        assert adapter.find_open_opportunity(company_id) is None

    def test_upsert_opportunity_creates_new(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp")
        opp_id = adapter.upsert_opportunity(company_id, {"name": "Test Opp", "stage": "SCREENING"})
        assert opp_id is not None
        opp = adapter.find_open_opportunity(company_id)
        assert opp is not None
        assert opp["id"] == opp_id

    def test_upsert_opportunity_idempotent(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp")
        id1 = adapter.upsert_opportunity(company_id, {"name": "Test Opp", "stage": "SCREENING"})
        id2 = adapter.upsert_opportunity(company_id, {"name": "Test Opp", "stage": "MEETING"})
        assert id1 == id2  # Same opportunity updated, not duplicated

    def test_add_note(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp")
        opp_id = adapter.upsert_opportunity(company_id, {"name": "Test Opp"})
        note_id = adapter.add_note(opp_id, "Test note", "opportunity")
        assert note_id is not None

    def test_add_task(self) -> None:
        adapter = FakeAdapter()
        company_id = adapter.upsert_company("Test Corp")
        opp_id = adapter.upsert_opportunity(company_id, {"name": "Test Opp"})
        task = TaskDraft(title="Follow up", body="Call them", due_at="2024-01-15")
        task_id = adapter.add_task(opp_id, task, "opportunity")
        assert task_id is not None

    def test_list_opportunities(self) -> None:
        adapter = FakeAdapter()
        company_id1 = adapter.upsert_company("Test Corp 1")
        company_id2 = adapter.upsert_company("Test Corp 2")
        adapter.upsert_opportunity(company_id1, {"name": "Opp 1", "stage": "SCREENING"})
        adapter.upsert_opportunity(company_id2, {"name": "Opp 2", "stage": "MEETING"})
        opps = adapter.list_opportunities()
        expected_count = 2
        assert len(opps) == expected_count

    def test_apply_plan_idempotent(self) -> None:
        """Running apply_plan twice should not create duplicate opportunities."""
        adapter = FakeAdapter()

        plan = UpdatePlan(
            company_name="Test Corp",
            opportunity_fields={"name": "Test Corp - Qualified", "stage": "MEETING"},
            note_markdown="Test note",
            tasks=[TaskDraft(title="Follow up", due_at="2024-01-15")],
            followup_email=EmailDraft(subject="Test", body="Test body"),
            missing_fields=[],
            stage=StageSuggestion(stage="qualified", reason="Test"),
        )

        # First apply
        result1 = apply_plan(plan, adapter)
        assert result1.company_id is not None
        assert result1.opportunity_id is not None

        # Second apply - should update same opportunity
        result2 = apply_plan(plan, adapter)
        assert result2.company_id == result1.company_id
        assert result2.opportunity_id == result1.opportunity_id

        # Verify only one opportunity exists
        opps = adapter.list_opportunities()
        assert len(opps) == 1


class TestCLI:
    """Test CLI commands."""

    def test_process_dry_run(self, tmp_path: Path) -> None:
        """Test process command with --dry-run."""
        transcript = tmp_path / "test.txt"
        transcript.write_text("John: Hello\nSarah: Hi there")

        fake_insights = CallInsights(
            company_name="Test Corp",
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
        )

        fake_plan = UpdatePlan(
            company_name="Test Corp",
            opportunity_fields={"name": "Test Corp - Discovery", "stage": "SCREENING"},
            note_markdown="Test note",
            tasks=[],
            followup_email=EmailDraft(subject="Test", body="Test"),
            missing_fields=["metrics"],
            stage=StageSuggestion(stage="discovery", reason="No pain"),
        )

        with (
            patch("crm_copilot.cli.extract_insights", return_value=fake_insights),
            patch("crm_copilot.cli.plan_updates", return_value=fake_plan),
        ):
            result = runner.invoke(app, ["process", str(transcript), "--dry-run"])

        assert result.exit_code == 0
        assert "Test Corp" in result.stdout
        assert "dry run" in result.stdout.lower()

    def test_process_with_output_file(self, tmp_path: Path) -> None:
        """Test process command with --out."""
        transcript = tmp_path / "test.txt"
        transcript.write_text("Test transcript")

        fake_insights = CallInsights(
            company_name="Test Corp",
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
        )

        fake_plan = UpdatePlan(
            company_name="Test Corp",
            opportunity_fields={"name": "Test Corp - Discovery", "stage": "SCREENING"},
            note_markdown="Test note",
            tasks=[],
            followup_email=EmailDraft(subject="Test", body="Test"),
            missing_fields=[],
            stage=StageSuggestion(stage="discovery", reason="No pain"),
        )

        out_file = tmp_path / "plan.json"

        with (
            patch("crm_copilot.cli.extract_insights", return_value=fake_insights),
            patch("crm_copilot.cli.plan_updates", return_value=fake_plan),
        ):
            result = runner.invoke(
                app,
                ["process", str(transcript), "--dry-run", "--out", str(out_file)],
            )

        assert result.exit_code == 0
        assert out_file.exists()
        saved_plan = json.loads(out_file.read_text())
        assert saved_plan["company_name"] == "Test Corp"

    def test_missing_command(self) -> None:
        """Test missing command."""
        with patch("crm_copilot.cli.settings.TWENTY_API_KEY", None):
            result = runner.invoke(app, ["missing"])
        assert result.exit_code == 0
        # With empty FakeAdapter, should show no opportunities
        assert "No opportunities found" in result.stdout or "Open Opportunities" in result.stdout

    def test_doctor_command(self) -> None:
        """Test doctor command."""
        with patch("crm_copilot.cli.settings.TWENTY_API_KEY", None):
            result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "LLM" in result.stdout
        assert "Twenty" in result.stdout

    def test_help(self) -> None:
        """Test help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "crm-copilot" in result.stdout
        assert "process" in result.stdout
        assert "missing" in result.stdout
        assert "doctor" in result.stdout