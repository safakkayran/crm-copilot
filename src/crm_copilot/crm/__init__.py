"""CRM package exports."""

from crm_copilot.crm.base import CRMAdapter
from crm_copilot.crm.fake import FakeAdapter

__all__ = ["CRMAdapter", "FakeAdapter"]