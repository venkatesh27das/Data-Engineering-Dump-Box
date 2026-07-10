"""Deterministic configuration validation. LLM recommendations cannot bypass it."""

from source_readiness_agent.config import Settings
from source_readiness_agent.models.contracts import (
    ConfigurationProposal,
    ValidationResult,
    ValidationStatus,
)
from source_readiness_agent.models.requests import ValidateConfigurationRequest
from source_readiness_agent.skills.checkpoint_validation import AutoLoaderConfigurationValidator
from source_readiness_agent.skills.path_validation import validate_landing
from source_readiness_agent.tools.repository import InMemoryRepository


class ValidationService:
    def __init__(self, repository: InMemoryRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self._checkpoints: dict[str, str] = {}

    def _unique(self, source_id: str, checkpoint: str) -> bool:
        owner = self._checkpoints.get(checkpoint)
        return owner in {None, source_id}

    def validate(
        self, request: ValidateConfigurationRequest
    ) -> tuple[ConfigurationProposal, ValidationResult]:
        if request.proposed_configuration is not None:
            proposal = request.proposed_configuration
        elif request.proposal_id:
            proposal = self.repository.get_proposal(request.proposal_id)
        else:
            raise ValueError("proposal_id or proposed_configuration is required")
        errors, warnings = validate_landing(
            proposal.landing_configuration, environment=proposal.environment
        )
        if (
            not proposal.bronze_configuration.target_catalog
            or not proposal.bronze_configuration.target_schema
        ):
            errors.append("Bronze target is not configured")
        if not proposal.bronze_configuration.source_to_manifest_mapping:
            errors.append("source-to-manifest mapping is empty")
        if not proposal.parser_routing_profile.primary_parser:
            errors.append("no eligible parser exists")
        if proposal.ingestion_configuration.ingestion_method.value == "DATABRICKS_AUTO_LOADER":
            auto = {
                "source_path": proposal.landing_configuration.root_path,
                "checkpoint_path": proposal.landing_configuration.checkpoint_path,
                "schema_location": proposal.landing_configuration.schema_location,
                "file_format": "binaryFile",
                "allowed_file_types": proposal.landing_configuration.allowed_extensions,
                "schema_evolution_mode": "rescue",
                "trigger_mode": "availableNow",
                "max_files_per_trigger": proposal.ingestion_configuration.batch_size,
                "idempotency_strategy": "sha256+source_id",
            }
            errors.extend(
                AutoLoaderConfigurationValidator(self._unique).validate(auto, proposal.source_id)
            )
        status = (
            ValidationStatus.INVALID
            if errors
            else ValidationStatus.VALID_WITH_WARNINGS
            if warnings
            else ValidationStatus.VALID
        )
        result = ValidationResult(
            status=status,
            errors=errors,
            warnings=warnings,
            remediation=[f"Correct: {error}" for error in errors],
        )
        proposal.validation_status = status
        proposal.warnings = warnings
        if not errors:
            self._checkpoints[proposal.landing_configuration.checkpoint_path] = proposal.source_id
        self.repository.save_proposal(proposal)
        return proposal, result
