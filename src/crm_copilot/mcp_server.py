"""MCP server for crm-copilot."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from crm_copilot.apply import apply_plan
from crm_copilot.config import settings
from crm_copilot.crm.fake import FakeAdapter
from crm_copilot.crm.twenty import TwentyAdapter
from crm_copilot.extract import extract_insights
from crm_copilot.llm import complete_json
from crm_copilot.models import ApplyResult, EmailDraft, UpdatePlan
from crm_copilot.planner import plan_updates


def _get_adapter() -> FakeAdapter | TwentyAdapter:
    """Get the appropriate CRM adapter based on configuration."""
    if settings.TWENTY_API_KEY:
        return TwentyAdapter()
    return FakeAdapter()


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    mcp = FastMCP("crm-copilot")

    @mcp.tool()
    async def process_transcript(transcript: str) -> UpdatePlan:
        """Process a sales call transcript and return the planned CRM updates.

        Args:
            transcript: The full transcript text of the sales call.

        Returns:
            UpdatePlan with opportunity fields, note, tasks, follow-up email, and missing fields.
        """
        return plan_updates(extract_insights(transcript))

    @mcp.tool()
    async def apply_plan_tool(plan: UpdatePlan) -> ApplyResult:
        """Apply a previously generated UpdatePlan to the CRM.

        Args:
            plan: The UpdatePlan to apply (from process_transcript).

        Returns:
            ApplyResult with IDs of created/updated records.
        """
        adapter = _get_adapter()
        result = apply_plan(plan, adapter)
        adapter.close()
        return result

    @mcp.tool()
    async def list_gaps() -> list[dict]:
        """List all open opportunities with their MEDDPICC gaps.

        Returns:
            List of opportunities with missing MEDDPICC fields.
        """
        adapter = _get_adapter()
        opportunities = adapter.list_opportunities()
        adapter.close()

        results = []
        for opp in opportunities:
            meddpicc = opp.get("meddpicc", {})
            if isinstance(meddpicc, str):
                try:
                    meddpicc = json.loads(meddpicc)
                except json.JSONDecodeError:
                    meddpicc = {}

            missing = []
            for field_name, field_data in meddpicc.items():
                if isinstance(field_data, dict) and field_data.get("value") is None:
                    missing.append(field_name)

            if missing:
                results.append({
                    "opportunity_id": opp.get("id"),
                    "opportunity_name": opp.get("name"),
                    "stage": opp.get("stage"),
                    "company_id": opp.get("companyId"),
                    "missing_fields": missing,
                })
        return results

    @mcp.tool()
    async def health_check() -> dict:
        """Check connectivity to LLM and Twenty CRM.

        Returns:
            Status of LLM and Twenty connections.
        """
        # Check LLM
        llm_status = "unknown"
        try:
            complete_json(
                system="Reply with JSON",
                user='Say {"status": "ok"}',
                schema=EmailDraft,
            )
            llm_status = "ok"
        except Exception as e:
            llm_status = f"fail: {e}"

        # Check Twenty
        twenty_status = "not configured"
        if settings.TWENTY_API_KEY:
            try:
                adapter = TwentyAdapter()
                twenty_status = "ok" if adapter.health_check() else "fail: health check failed"
                adapter.close()
            except Exception as e:
                twenty_status = f"fail: {e}"

        return {
            "llm": llm_status,
            "twenty": twenty_status,
            "model": settings.LLM_MODEL,
        }

    return mcp


def main() -> None:
    """Entry point for the MCP server."""
    mcp = create_mcp_server()
    mcp.run()


if __name__ == "__main__":
    main()