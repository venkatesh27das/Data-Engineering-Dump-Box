"""Controlled, disabled-by-default configuration proposal generation."""

from __future__ import annotations

from uuid import uuid4

from source_readiness_agent.config import Settings
from source_readiness_agent.models.contracts import (
    BronzeConfiguration,
    ConfigurationProposal,
    IngestionConfiguration,
    IngestionMethod,
    LandingConfiguration,
    MetadataProfile,
    ParserRoutingProfile,
    ReadinessAssessment,
    SourceDefinition,
)


def generate_configuration(
    source: SourceDefinition,
    assessment: ReadinessAssessment,
    settings: Settings,
    environment: str,
    strategy: dict[str, object],
    metadata: MetadataProfile,
    primary_parser: str,
    fallbacks: list[str],
    schedule: str,
    version: int,
    actor: str,
) -> ConfigurationProposal:
    pattern = f"/landing/{environment}/{{source_system}}/{{application}}/{{use_case}}/{{ingestion_date}}/{{batch_id}}/"
    landing = LandingConfiguration(
        storage_account_reference="configured_storage_account",
        filesystem="configured_landing_filesystem",
        root_path=pattern,
        partition_pattern="/landing/{source_system}/{application}/{use_case}/{ingestion_date}/{batch_id}/",
        source_partition=source.source_id,
        retention_policy="configured_retention_policy",
        checkpoint_path=f"/checkpoints/{environment}/{source.source_id}/",
        schema_location=f"/schemas/{environment}/{source.source_id}/",
        quarantine_path=f"/quarantine/{environment}/{source.source_id}/",
        allowed_extensions=sorted(
            {p.file_type for p in assessment.source_profile.file_profiles if p.supported}
        )
        if assessment.source_profile
        else [],
    )
    bronze = BronzeConfiguration(
        target_catalog=settings.databricks_catalog,
        target_schema=settings.databricks_bronze_schema,
        volume_name=f"source_{source.source_id.lower().replace('-', '_')}",
        manifest_table="file_manifest",
        exception_table="file_exceptions",
        parser_config_table="parser_configuration",
        lineage_table="file_lineage",
        source_to_manifest_mapping={
            "object_id": "source_object_id",
            "path_or_uri": "source_uri",
            "file_name": "file_name",
            "file_size_bytes": "size_bytes",
            "checksum_if_available": "sha256",
        },
        registration_rules={
            "preserve_raw_bytes": True,
            "binary_in_delta_rows": False,
            "immutable": True,
        },
        retry_policy={"maximum_attempts": 3},
        dlq_policy={"enabled": True},
    )
    method = IngestionMethod(str(strategy["selected_strategy"]))
    ingestion = IngestionConfiguration(
        ingestion_method=method,
        connector_id=source.connection_reference,
        schedule=schedule,
        incremental_strategy="CHECKPOINT"
        if method == IngestionMethod.DATABRICKS_AUTO_LOADER
        else "BATCH_ID",
        checkpoint_path=landing.checkpoint_path
        if method == IngestionMethod.DATABRICKS_AUTO_LOADER
        else None,
        landing_configuration=landing,
        failure_handling={"retry": 3, "dlq": True},
        enabled=False,
    )
    routing = ParserRoutingProfile(
        eligible_file_types=landing.allowed_extensions,
        primary_parser=primary_parser,
        fallback_parsers=fallbacks,
        quality_thresholds={"minimum_parse_success": 0.90, "minimum_metadata_completeness": 0.98},
    )
    proposal_id = f"PROP-{uuid4().hex[:12].upper()}"
    return ConfigurationProposal(
        proposal_id=proposal_id,
        source_id=source.source_id,
        environment=environment,
        version=version,
        assessment_id=assessment.assessment_id,
        ingestion_configuration=ingestion,
        landing_configuration=landing,
        bronze_configuration=bronze,
        parser_routing_profile=routing,
        metadata_profile=metadata,
        workflow_parameters={
            "source_id": source.source_id,
            "proposal_id": proposal_id,
            "dry_run": True,
        },
        created_by=actor,
    )
