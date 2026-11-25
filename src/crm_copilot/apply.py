"""Apply module: apply UpdatePlan using a CRM adapter."""

from __future__ import annotations

from crm_copilot.crm.base import CRMAdapter  # noqa: TC001
from crm_copilot.models import ApplyResult, UpdatePlan  # noqa: TC001


def apply_plan(plan: UpdatePlan, adapter: CRMAdapter) -> ApplyResult:
    """
    Apply a plan to the CRM using the given adapter.

    Idempotent per company + opportunity: running twice must not create
    a second opportunity for the same company.

    Args:
        plan: The update plan to apply
        adapter: CRM adapter implementation (FakeAdapter or TwentyAdapter)

    Returns:
        ApplyResult with IDs of created/updated records
    """
    return adapter.apply_plan(plan)