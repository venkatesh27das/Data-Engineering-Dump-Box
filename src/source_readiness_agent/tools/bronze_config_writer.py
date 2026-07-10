"""Approval-gated writer boundary; production uses UC functions or parameterized SQL."""

from source_readiness_agent.models.contracts import Approval, AuditMetadata, ConfigurationProposal

from .base import require_approval
from .repository import InMemoryRepository


class BronzeConfigurationWriter:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def register_approved_source_configuration(
        self, proposal: ConfigurationProposal, approval: Approval, audit: AuditMetadata
    ) -> ConfigurationProposal:
        require_approval(approval, audit)
        return self.repository.activate(proposal)
