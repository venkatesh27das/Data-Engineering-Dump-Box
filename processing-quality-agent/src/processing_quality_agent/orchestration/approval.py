from processing_quality_agent.models.recovery import ApprovalContext
from processing_quality_agent.tools.base import ApprovalRequiredError


def require_approval(approval: ApprovalContext) -> None:
    if not approval.valid():
        raise ApprovalRequiredError(
            "an approved flag, approval reference, and approver identity are required"
        )
