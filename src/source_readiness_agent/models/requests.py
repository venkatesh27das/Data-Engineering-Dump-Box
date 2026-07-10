"""API request contracts."""

from typing import Any

from pydantic import Field

from .contracts import Approval, ConfigurationProposal, SamplePolicy, SourceDefinition, StrictModel


class AssessSourceRequest(StrictModel):
    source: SourceDefinition
    sample_policy: SamplePolicy = Field(default_factory=SamplePolicy)
    dry_run: bool = True
    actor: str = "local-engineer"
    reason: str = "source readiness assessment"
    correlation_id: str | None = None


class GenerateConfigurationRequest(StrictModel):
    assessment_id: str
    ingestion_preference: str = "AUTO"
    desired_ingestion_schedule: str = "0 0 * * *"
    target_environment: str = "dev"
    allowed_parsers: list[str] = Field(default_factory=list)
    metadata_requirements: list[str] = Field(default_factory=list)
    target_landing_configuration: dict[str, Any] = Field(default_factory=dict)
    generate_adf_parameters: bool = True
    generate_databricks_parameters: bool = True
    actor: str = "local-engineer"
    reason: str = "generate configuration"
    correlation_id: str | None = None


class ValidateConfigurationRequest(StrictModel):
    proposal_id: str | None = None
    proposed_configuration: ConfigurationProposal | None = None
    validation_profile: str = "default"
    actor: str = "local-engineer"
    correlation_id: str | None = None


class SampleRunRequest(StrictModel):
    proposal_id: str
    sample_size: int = Field(default=25, ge=1, le=1000)
    approval: Approval
    dry_run: bool = True
    actor: str = "local-engineer"
    correlation_id: str | None = None


class ActivateConfigurationRequest(StrictModel):
    validated_configuration_id: str
    successful_sample_run_id: str
    approval: Approval
    change_reference: str
    actor: str = "local-engineer"
    correlation_id: str | None = None
