"""Validated domain contracts used across transport, orchestration, and adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceType(StrEnum):
    ADLS = "ADLS"
    SHAREPOINT = "SHAREPOINT"
    SFTP = "SFTP"
    API = "API"
    MOCK = "MOCK"


class Modality(StrEnum):
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"
    TEXT = "TEXT"
    STRUCTURED = "STRUCTURED"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    UNKNOWN = "UNKNOWN"


class ReadinessStatus(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    SAMPLE_RUN_FAILED = "SAMPLE_RUN_FAILED"
    NOT_READY = "NOT_READY"


class ValidationStatus(StrEnum):
    NOT_VALIDATED = "NOT_VALIDATED"
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"


class RunStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class SamplingStrategy(StrEnum):
    RANDOM = "RANDOM"
    STRATIFIED_BY_FILE_TYPE = "STRATIFIED_BY_FILE_TYPE"
    STRATIFIED_BY_SIZE = "STRATIFIED_BY_SIZE"
    STRATIFIED_BY_MODALITY = "STRATIFIED_BY_MODALITY"
    RISK_BASED = "RISK_BASED"
    USER_SELECTED = "USER_SELECTED"
    HYBRID = "HYBRID"


class IngestionMethod(StrEnum):
    ADF_BATCH = "ADF_BATCH"
    DATABRICKS_CONNECTOR_BATCH = "DATABRICKS_CONNECTOR_BATCH"
    DATABRICKS_AUTO_LOADER = "DATABRICKS_AUTO_LOADER"
    API_PULL = "API_PULL"
    SFTP_PULL = "SFTP_PULL"
    MANUAL_CONTROLLED_UPLOAD = "MANUAL_CONTROLLED_UPLOAD"


class SourceDefinition(StrictModel):
    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    source_name: str = Field(min_length=1, max_length=256)
    source_type: SourceType
    source_system: str = "unknown"
    connection_reference: str
    source_location: str
    business_owner: str
    technical_owner: str
    expected_modalities: list[Modality] = Field(default_factory=list)
    expected_file_types: list[str] = Field(default_factory=list)
    expected_volume: int | None = Field(default=None, ge=0)
    ingestion_frequency: str = "ON_DEMAND"
    retention_requirement: str | None = None
    metadata_requirements: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("source_location")
    @classmethod
    def reject_unsafe_location(cls, value: str) -> str:
        lowered = value.lower()
        if "\x00" in value or ".." in value.replace("%2e", ".").lower().split("/"):
            raise ValueError("path traversal is not allowed")
        if not lowered.startswith(("abfss://", "https://", "sftp://", "file://", "mock://")):
            raise ValueError("unsupported source URI scheme")
        return value


class SourceObject(StrictModel):
    object_id: str
    source_id: str
    path_or_uri: str
    file_name: str
    extension: str = ""
    reported_mime_type: str | None = None
    file_size_bytes: int = Field(ge=0)
    last_modified_at: datetime | None = None
    checksum_if_available: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class SourceObjectMetadata(StrictModel):
    object_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class SourceListRequest(StrictModel):
    source: SourceDefinition
    maximum_objects: int = Field(default=100, ge=1, le=10_000)
    continuation_token: str | None = None


class SampleReadRequest(StrictModel):
    source_object: SourceObject
    maximum_bytes: int = Field(default=1_048_576, ge=1, le=10_485_760)


class SourceSample(StrictModel):
    object_id: str
    content: bytes = Field(repr=False)
    truncated: bool


class ConnectionValidationResult(StrictModel):
    accessible: bool
    allowed: bool
    permissions: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class SourceInventoryEstimate(StrictModel):
    estimated_file_count: int = Field(ge=0)
    estimated_total_bytes: int = Field(ge=0)
    complete: bool = False


class FileProfile(StrictModel):
    object_id: str
    file_name: str
    file_type: str
    detected_mime_type: str
    reported_mime_type: str | None = None
    mime_match: bool
    size_bytes: int = Field(ge=0)
    zero_byte: bool
    encrypted_or_password_protected: bool = False
    corrupt_signal: bool = False
    modality: Modality
    scanned_probability: float = Field(default=0, ge=0, le=1)
    page_estimate: int | None = Field(default=None, ge=0)
    layout_complexity: float = Field(default=0, ge=0, le=1)
    table_probability: float = Field(default=0, ge=0, le=1)
    image_probability: float = Field(default=0, ge=0, le=1)
    supported: bool
    issues: list[str] = Field(default_factory=list)
    metadata_completeness: float = Field(default=1, ge=0, le=1)
    duplicate_candidate: bool = False


class SourceProfile(StrictModel):
    source_id: str
    estimated_file_count: int = 0
    estimated_total_bytes: int = 0
    sampled_file_count: int = 0
    file_type_distribution: dict[str, int] = Field(default_factory=dict)
    modality_distribution: dict[str, int] = Field(default_factory=dict)
    size_distribution: dict[str, int] = Field(default_factory=dict)
    unsupported_file_count: int = 0
    zero_byte_count: int = 0
    corrupt_candidate_count: int = 0
    duplicate_candidate_count: int = 0
    complex_document_ratio: float = 0
    scanned_document_ratio: float = 0
    metadata_completeness: float = 0
    access_validation: ConnectionValidationResult
    file_profiles: list[FileProfile] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class SamplePolicy(StrictModel):
    strategy: SamplingStrategy = SamplingStrategy.HYBRID
    maximum_files: int = Field(default=25, ge=1, le=1000)
    maximum_total_bytes: int = Field(default=524_288_000, ge=1)
    maximum_individual_file_size: int = Field(default=104_857_600, ge=1)
    maximum_listing_pages: int = Field(default=10, ge=1, le=100)
    operation_timeout_seconds: int = Field(default=120, ge=1, le=3600)


class SampleSelection(StrictModel):
    source_object: SourceObject
    reasons: list[str]


class LandingConfiguration(StrictModel):
    storage_account_reference: str
    filesystem: str
    root_path: str
    partition_pattern: str
    source_partition: str
    ingestion_date_partition: str = "{ingestion_date}"
    batch_partition: str = "{batch_id}"
    append_only: bool = True
    retention_policy: str
    checkpoint_path: str
    schema_location: str
    quarantine_path: str
    allowed_extensions: list[str]


class BronzeConfiguration(StrictModel):
    target_catalog: str
    target_schema: str
    volume_name: str
    manifest_table: str
    exception_table: str
    parser_config_table: str
    lineage_table: str
    source_to_manifest_mapping: dict[str, str]
    hash_algorithm: str = "SHA-256"
    registration_rules: dict[str, Any] = Field(default_factory=dict)
    duplicate_policy: str = "REGISTER_REFERENCE"
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    dlq_policy: dict[str, Any] = Field(default_factory=dict)


class IngestionConfiguration(StrictModel):
    ingestion_method: IngestionMethod
    connector_id: str
    schedule: str
    batch_size: int = Field(default=100, ge=1)
    maximum_concurrency: int = Field(default=4, ge=1, le=100)
    incremental_strategy: str
    watermark_column: str | None = None
    checkpoint_path: str | None = None
    source_filter: dict[str, Any] = Field(default_factory=dict)
    landing_configuration: LandingConfiguration
    failure_handling: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False


class ParserRoutingProfile(StrictModel):
    document_class: str = "GENERAL"
    eligible_file_types: list[str]
    primary_parser: str
    fallback_parsers: list[str] = Field(default_factory=list)
    parser_config: dict[str, Any] = Field(default_factory=dict)
    quality_thresholds: dict[str, float] = Field(default_factory=dict)
    maximum_attempts: int = Field(default=2, ge=1)
    unsupported_behaviour: str = "QUARANTINE"


class MetadataProfile(StrictModel):
    mandatory_source_fields: list[str]
    mandatory_document_fields: list[str]
    inferred_fields: list[str] = Field(default_factory=list)
    static_tags: dict[str, str] = Field(default_factory=dict)
    document_type_rules: dict[str, Any] = Field(default_factory=dict)
    business_domain_rules: dict[str, Any] = Field(default_factory=dict)
    source_metadata_mapping: dict[str, str] = Field(default_factory=dict)
    completeness_threshold: float = Field(default=0.9, ge=0, le=1)
    provenance: dict[str, str] = Field(default_factory=dict)


class ConfigurationProposal(StrictModel):
    proposal_id: str
    source_id: str
    environment: str
    version: int = Field(ge=1)
    parent_version: int | None = None
    assessment_id: str
    ingestion_configuration: IngestionConfiguration
    landing_configuration: LandingConfiguration
    bronze_configuration: BronzeConfiguration
    parser_routing_profile: ParserRoutingProfile
    metadata_profile: MetadataProfile
    workflow_parameters: dict[str, Any] = Field(default_factory=dict)
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    warnings: list[str] = Field(default_factory=list)
    approval_required: bool = True
    change_summary: str = "Initial proposal"
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_by: str | None = None
    approved_by: str | None = None
    approval_reference: str | None = None
    active: bool = False


class Approval(StrictModel):
    approved: bool = False
    approval_reference: str | None = None
    approved_by: str | None = None
    reason: str | None = None


class SampleRun(StrictModel):
    sample_run_id: str
    proposal_id: str
    source_id: str
    selected_objects: list[str]
    selection_strategy: SamplingStrategy
    workflow_type: str
    external_run_id: str | None = None
    start_time: datetime = Field(default_factory=utc_now)
    completion_time: datetime | None = None
    status: RunStatus = RunStatus.PLANNED
    bronze_registered_count: int = 0
    parsed_count: int = 0
    failed_count: int = 0
    unsupported_count: int = 0
    quality_summary: dict[str, float] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    idempotency_key: str
    dry_run: bool = True


class Evidence(StrictModel):
    category: str
    message: str
    object_id: str | None = None


class ReadinessAssessment(StrictModel):
    assessment_id: str
    source_id: str
    readiness_score: float = Field(ge=0, le=100)
    readiness_status: ReadinessStatus
    category_scores: dict[str, float]
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    source_profile: SourceProfile | None = None
    recommended_ingestion_strategy: dict[str, Any] | None = None
    assessed_at: datetime = Field(default_factory=utc_now)


class ValidationResult(StrictModel):
    status: ValidationStatus
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)


class AuditMetadata(StrictModel):
    actor: str
    reason: str
    correlation_id: str
    approval_reference: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class OperationResult(StrictModel):
    correlation_id: str
    operation_mode: str
    source_summary: dict[str, Any] = Field(default_factory=dict)
    source_profile: SourceProfile | None = None
    readiness_assessment: ReadinessAssessment | None = None
    configuration_proposal: ConfigurationProposal | None = None
    validation_result: ValidationResult | None = None
    sample_run: SampleRun | None = None
    approval_required: bool = False
    next_actions: list[str] = Field(default_factory=list)
    audit_metadata: AuditMetadata
