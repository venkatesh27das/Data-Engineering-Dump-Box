"""Feature-flagged, approved configuration activation."""

from source_readiness_agent.config import Settings
from source_readiness_agent.models.contracts import (
    AuditMetadata,
    ConfigurationProposal,
    RunStatus,
    ValidationStatus,
)
from source_readiness_agent.models.requests import ActivateConfigurationRequest
from source_readiness_agent.tools.base import require_approval
from source_readiness_agent.tools.repository import InMemoryRepository


class ActivationService:
    def __init__(self, repository: InMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def activate(
        self, request: ActivateConfigurationRequest, correlation_id: str
    ) -> ConfigurationProposal:
        if not self.settings.activation_enabled:
            raise PermissionError("configuration activation is feature-flagged and disabled")
        audit = AuditMetadata(
            actor=request.actor,
            reason="configuration activation",
            correlation_id=correlation_id,
            approval_reference=request.approval.approval_reference,
        )
        require_approval(request.approval, audit)
        proposal = self.repository.get_proposal(request.validated_configuration_id)
        run = self.repository.sample_runs[request.successful_sample_run_id]
        if proposal.validation_status not in {
            ValidationStatus.VALID,
            ValidationStatus.VALID_WITH_WARNINGS,
        }:
            raise ValueError("configuration is not validated")
        if run.proposal_id != proposal.proposal_id or run.status != RunStatus.SUCCEEDED:
            raise ValueError("a successful sample run for this proposal is required")
        proposal.approved_by = request.approval.approved_by
        proposal.approval_reference = request.approval.approval_reference
        return self.repository.activate(proposal)
