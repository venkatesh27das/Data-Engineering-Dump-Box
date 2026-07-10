"""Versioned proposal generation."""

from source_readiness_agent.config import Settings
from source_readiness_agent.models.contracts import ConfigurationProposal
from source_readiness_agent.models.requests import GenerateConfigurationRequest
from source_readiness_agent.skills.configuration_generation import generate_configuration
from source_readiness_agent.skills.ingestion_strategy import recommend_ingestion
from source_readiness_agent.skills.metadata_profile_generation import generate_metadata_profile
from source_readiness_agent.skills.parser_eligibility import default_registry
from source_readiness_agent.tools.repository import InMemoryRepository


class ConfigurationService:
    def __init__(self, repository: InMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def generate(self, request: GenerateConfigurationRequest) -> ConfigurationProposal:
        assessment = self.repository.get_assessment(request.assessment_id)
        source = self.repository.sources[assessment.source_id]
        profile = assessment.source_profile
        if profile is None:
            raise ValueError("assessment has no source profile")
        strategy = recommend_ingestion(source, profile, request.ingestion_preference)
        metadata = generate_metadata_profile(source, request.metadata_requirements)
        registry = default_registry()
        allowed = set(request.allowed_parsers) or None
        candidates = []
        for file_profile in profile.file_profiles:
            candidates.extend(registry.eligible(file_profile, request.target_environment, allowed))
        unique = list(dict.fromkeys(candidate.parser_id for candidate in candidates))
        if not unique:
            raise ValueError("no eligible parser exists for the sampled supported files")
        version = self.repository.next_version(source.source_id, request.target_environment)
        proposal = generate_configuration(
            source,
            assessment,
            self.settings,
            request.target_environment,
            strategy,
            metadata,
            unique[0],
            unique[1:],
            request.desired_ingestion_schedule,
            version,
            request.actor,
        )
        proposal.workflow_parameters.update(
            {
                "generate_adf_parameters": request.generate_adf_parameters,
                "generate_databricks_parameters": request.generate_databricks_parameters,
            }
        )
        self.repository.save_proposal(proposal)
        return proposal
