"""Twenty CRM adapter implementation."""

from __future__ import annotations

import os
from typing import Any

import httpx

from crm_copilot.crm.base import CRMAdapter
from crm_copilot.models import ApplyResult, TaskDraft, UpdatePlan


class TwentyAdapter(CRMAdapter):
    """Twenty CRM REST API adapter."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        rest_prefix: str | None = None,
    ) -> None:
        self.base_url = base_url or os.getenv("TWENTY_BASE_URL", "http://localhost:3000")
        self.api_key = api_key or os.getenv("TWENTY_API_KEY")
        self.rest_prefix = rest_prefix or os.getenv("TWENTY_REST_PREFIX", "/rest")

        if not self.api_key:
            raise ValueError("TWENTY_API_KEY not set")

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _request(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None
    ) -> dict:
        url = f"{self.rest_prefix}{path}"
        response = self._client.request(method, url, json=json_data, params=params)
        response.raise_for_status()
        return response.json()

    def find_company(self, name: str) -> str | None:
        """Find company by exact name match."""
        result = self._request(
            "GET",
            "/companies",
            params={"filter": f"name[eq]:{name}", "limit": 1, "fields": "id,name"},
        )
        companies = result.get("data", {}).get("companies", [])
        return companies[0]["id"] if companies else None

    def upsert_company(self, name: str, domain: str | None = None) -> str:
        """Create or find existing company."""
        existing = self.find_company(name)
        if existing:
            return existing

        domain_name = None
        if domain:
            domain_name = {
                "primaryLinkUrl": domain,
                "primaryLinkLabel": "",
                "secondaryLinks": [],
            }

        data: dict[str, Any] = {"name": name}
        if domain_name:
            data["domainName"] = domain_name

        result = self._request("POST", "/companies", json_data=data)
        return result["data"]["createCompany"]["id"]

    def find_open_opportunity(self, company_id: str) -> dict | None:
        """Find open opportunity for a company (stage != CUSTOMER)."""
        result = self._request(
            "GET",
            "/opportunities",
            params={
                "filter": f"companyId[eq]:{company_id},stage[neq]:CUSTOMER",
                "limit": 1,
            },
        )
        opportunities = result.get("data", {}).get("opportunities", [])
        return opportunities[0] if opportunities else None

    def upsert_opportunity(self, company_id: str, fields: dict) -> str:
        """Create or update opportunity for a company."""
        existing = self.find_open_opportunity(company_id)
        if existing:
            opp_id = existing["id"]
            # Only update allowed fields
            update_data = {}
            for key in ["name", "stage", "amount", "closeDate", "meddpicc"]:
                if key in fields:
                    update_data[key] = fields[key]
            if update_data:
                self._request("PATCH", f"/opportunities/{opp_id}", json_data=update_data)
            return opp_id

        # Create new opportunity
        create_data = {"companyId": company_id, **fields}
        result = self._request("POST", "/opportunities", json_data=create_data)
        return result["data"]["createOpportunity"]["id"]

    def add_note(
        self, target_id: str, markdown: str, target_type: str = "opportunity"
    ) -> str:
        """Create a note and link it to target."""
        # Create note
        note_result = self._request(
            "POST",
            "/notes",
            json_data={"title": "Call notes", "bodyV2": {"markdown": markdown}},
        )
        note_id = note_result["data"]["createNote"]["id"]

        # Link note to target
        note_target_data = {"noteId": note_id}
        if target_type == "opportunity":
            note_target_data["targetOpportunityId"] = target_id
        elif target_type == "company":
            note_target_data["targetCompanyId"] = target_id

        self._request("POST", "/noteTargets", json_data=note_target_data)
        return note_id

    def add_task(
        self, target_id: str, task: TaskDraft, target_type: str = "opportunity"
    ) -> str:
        """Create a task and link it to target."""
        task_data = {
            "title": task.title,
            "bodyV2": {"markdown": task.body or ""},
            "status": "TODO",
        }
        if task.due_at:
            task_data["dueAt"] = task.due_at

        task_result = self._request("POST", "/tasks", json_data=task_data)
        task_id = task_result["data"]["createTask"]["id"]

        # Link task to target
        task_target_data = {"taskId": task_id}
        if target_type == "opportunity":
            task_target_data["targetOpportunityId"] = target_id
        elif target_type == "company":
            task_target_data["targetCompanyId"] = target_id

        self._request("POST", "/taskTargets", json_data=task_target_data)
        return task_id

    def list_opportunities(self) -> list[dict]:
        """List all open opportunities with MEDDPICC data."""
        result = self._request(
            "GET",
            "/opportunities",
            params={
                "filter": "stage[neq]:CUSTOMER",
                "limit": 60,
            },
        )
        return result.get("data", {}).get("opportunities", [])

    def apply_plan(self, plan: UpdatePlan) -> ApplyResult:
        """Apply a complete update plan. Idempotent per company + opportunity."""
        result = ApplyResult()

        # 1. Find or create company
        company_id = self.find_company(plan.company_name)
        if not company_id:
            company_id = self.upsert_company(plan.company_name)
        result.company_id = company_id

        # 2. Prepare opportunity fields (convert amount to micros if needed)
        opp_fields = dict(plan.opportunity_fields)
        if "amount" in opp_fields and isinstance(opp_fields["amount"], (int, float)):
            opp_fields["amount"] = {
                "amountMicros": int(opp_fields["amount"] * 1_000_000),
                "currencyCode": "USD",
            }

        # 3. Upsert opportunity (idempotent)
        opportunity_id = self.upsert_opportunity(company_id, opp_fields)
        result.opportunity_id = opportunity_id
        result.updated = True

        # 4. Add note linked to opportunity (and company)
        if plan.note_markdown:
            note_id = self.add_note(opportunity_id, plan.note_markdown, "opportunity")
            result.note_id = note_id
            # Also link to company
            self.add_note(company_id, plan.note_markdown, "company")

        # 5. Add tasks
        for task in plan.tasks:
            task_id = self.add_task(opportunity_id, task, "opportunity")
            result.task_ids.append(task_id)
            # Also link to company
            self.add_task(company_id, task, "company")

        return result

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def health_check(self) -> bool:
        """Check if Twenty API is reachable and credentials are valid."""
        try:
            self._request("GET", "/companies", params={"limit": 1})
            return True
        except Exception:
            return False

    def __enter__(self) -> TwentyAdapter:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()