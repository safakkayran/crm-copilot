"""CRM Adapter Protocol - base interface for CRM implementations."""

from __future__ import annotations

from typing import Protocol

from crm_copilot.models import ApplyResult, TaskDraft, UpdatePlan  # noqa: TC001


class CRMAdapter(Protocol):
    """Protocol for CRM adapters. Implementations must provide all methods."""

    def find_company(self, name: str) -> str | None:
        """Find company by name. Returns company_id or None."""

    def upsert_company(self, name: str, domain: str | None = None) -> str:
        """Create or update company. Returns company_id."""

    def find_open_opportunity(self, company_id: str) -> dict | None:
        """Find open opportunity for a company. Returns opportunity dict or None."""

    def upsert_opportunity(self, company_id: str, fields: dict) -> str:
        """Create or update opportunity. Returns opportunity_id."""

    def add_note(self, target_id: str, markdown: str, target_type: str = "opportunity") -> str:
        """Add a note linked to target (opportunity or company). Returns note_id."""

    def add_task(self, target_id: str, task: TaskDraft, target_type: str = "opportunity") -> str:
        """Add a task linked to target. Returns task_id."""

    def list_opportunities(self) -> list[dict]:
        """List all opportunities with their MEDDPICC data."""

    def apply_plan(self, plan: UpdatePlan) -> ApplyResult:
        """Apply a complete update plan. Returns ApplyResult with created/updated IDs."""