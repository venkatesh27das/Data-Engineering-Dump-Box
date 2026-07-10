"""Tool contracts and safe errors."""

from dataclasses import dataclass
from typing import Any, Protocol

from source_readiness_agent.models.contracts import Approval, AuditMetadata


class ToolError(RuntimeError):
    """Safe tool failure without sensitive context."""


class ApprovalRequired(ToolError):
    """Raised before any unapproved action."""


def require_approval(approval: Approval, audit: AuditMetadata) -> None:
    if not approval.approved or not approval.approval_reference or not approval.approved_by:
        raise ApprovalRequired("explicit approval, approval reference, and approver are required")
    if audit.approval_reference and audit.approval_reference != approval.approval_reference:
        raise ApprovalRequired("audit and approval references do not match")


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    mutating: bool
    approval_required: bool


class GovernedTool(Protocol):
    descriptor: ToolDescriptor

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]: ...
