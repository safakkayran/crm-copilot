"""CRM package exports."""

from crm_copilot.crm.base import CRMAdapter
from crm_copilot.crm.fake import FakeAdapter
from crm_copilot.crm.twenty import TwentyAdapter

__all__ = ["CRMAdapter", "FakeAdapter", "TwentyAdapter"]