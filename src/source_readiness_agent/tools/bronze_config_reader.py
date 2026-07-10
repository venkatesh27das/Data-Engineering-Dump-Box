from source_readiness_agent.models.contracts import ConfigurationProposal

from .repository import InMemoryRepository


class BronzeConfigurationReader:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository

    def get_existing_source_configuration(self, proposal_id: str) -> ConfigurationProposal:
        return self.repository.get_proposal(proposal_id)
