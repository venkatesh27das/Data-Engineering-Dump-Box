from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from processing_quality_agent.models.recovery import ApprovalContext


class ToolError(RuntimeError):
    pass


class ApprovalRequiredError(ToolError):
    pass


class UnsafeSourceURIError(ToolError):
    pass


@dataclass(frozen=True)
class WriteContext:
    actor: str
    approval: ApprovalContext
    reason: str
    correlation_id: str
    dry_run: bool = False

    def validate(self) -> None:
        if (
            not self.actor
            or not self.reason
            or not self.correlation_id
            or not self.approval.valid()
        ):
            raise ApprovalRequiredError(
                "write requires actor, reason, correlation ID, and valid approval"
            )


class Tool(Protocol):
    name: str
    description: str
    state_changing: bool

    async def invoke(self, **kwargs: Any) -> Any: ...
