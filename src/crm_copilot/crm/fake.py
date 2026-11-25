"""Fake in-memory CRM adapter for testing and dry-run mode."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from crm_copilot.crm.base import CRMAdapter
from crm_copilot.models import ApplyResult, TaskDraft, UpdatePlan


class FakeAdapter(CRMAdapter):
    """In-memory CRM adapter for testing and --dry-run."""

    def __init__(self) -> None:
        self.companies: dict[str, dict[str, Any]] = {}
        self.companies_by_id: dict[str, dict[str, Any]] = {}
        self.opportunities: dict[str, dict[str, Any]] = {}
        self.notes: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.note_targets: list[dict[str, str]] = []
        self.task_targets: list[dict[str, str]] = []

    def find_company(self, name: str) -> str | None:
        company = self.companies.get(name)
        return company["id"] if company else None

    def upsert_company(self, name: str, domain: str | None = None) -> str:
        if name in self.companies:
            return self.companies[name]["id"]

        company_id = str(uuid.uuid4())
        company = {
            "id": company_id,
            "name": name,
            "domain": domain,
        }
        self.companies[name] = company
        self.companies_by_id[company_id] = company
        return company_id

    def find_open_opportunity(self, company_id: str) -> dict | None:
        for opp in self.opportunities.values():
            if opp["company_id"] == company_id and opp.get("stage") != "CUSTOMER":
                return deepcopy(opp)
        return None

    def upsert_opportunity(self, company_id: str, fields: dict) -> str:
        # Check if open opportunity already exists for this company
        existing = self.find_open_opportunity(company_id)
        if existing:
            opp_id = existing["id"]
            self.opportunities[opp_id].update(fields)
            return opp_id

        # Create new opportunity
        opp_id = str(uuid.uuid4())
        opportunity = {
            "id": opp_id,
            "company_id": company_id,
            **fields,
        }
        self.opportunities[opp_id] = opportunity
        return opp_id

    def add_note(self, target_id: str, markdown: str, target_type: str = "opportunity") -> str:
        note_id = str(uuid.uuid4())
        note = {
            "id": note_id,
            "target_id": target_id,
            "target_type": target_type,
            "markdown": markdown,
        }
        self.notes[note_id] = note
        return note_id

    def add_task(self, target_id: str, task: TaskDraft, target_type: str = "opportunity") -> str:
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "target_id": target_id,
            "target_type": target_type,
            "title": task.title,
            "body": task.body,
            "due_at": task.due_at,
            "status": "TODO",
        }
        self.tasks[task_id] = task_data
        return task_id

    def list_opportunities(self) -> list[dict]:
        return [deepcopy(opp) for opp in self.opportunities.values()]

    def apply_plan(self, plan: UpdatePlan) -> ApplyResult:
        """Apply a complete update plan. Idempotent per company + opportunity."""
        result = ApplyResult()

        # 1. Find or create company
        company_id = self.find_company(plan.company_name)
        if not company_id:
            company_id = self.upsert_company(plan.company_name)
        result.company_id = company_id

        # 2. Upsert opportunity (idempotent - won't create duplicate)
        opportunity_id = self.upsert_opportunity(company_id, plan.opportunity_fields)
        result.opportunity_id = opportunity_id
        result.updated = True

        # 3. Add note linked to opportunity
        if plan.note_markdown:
            note_id = self.add_note(opportunity_id, plan.note_markdown, "opportunity")
            result.note_id = note_id
            # Also link to company
            self.note_targets.append({
                "note_id": note_id,
                "opportunity_id": opportunity_id,
                "company_id": company_id,
            })

        # 4. Add tasks
        for task in plan.tasks:
            task_id = self.add_task(opportunity_id, task, "opportunity")
            result.task_ids.append(task_id)
            self.task_targets.append({
                "task_id": task_id,
                "opportunity_id": opportunity_id,
                "company_id": company_id,
            })

        return result