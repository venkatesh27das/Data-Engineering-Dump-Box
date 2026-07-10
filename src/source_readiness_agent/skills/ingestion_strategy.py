"""Policy-based ingestion recommendation; it does not assume one universal mechanism."""

from source_readiness_agent.models.contracts import (
    IngestionMethod,
    SourceDefinition,
    SourceProfile,
    SourceType,
)


def recommend_ingestion(
    source: SourceDefinition, profile: SourceProfile, preference: str = "AUTO"
) -> dict[str, object]:
    if preference != "AUTO":
        try:
            selected = IngestionMethod(preference)
        except ValueError as exc:
            raise ValueError("unsupported ingestion preference") from exc
    elif source.source_type == SourceType.API:
        selected = IngestionMethod.API_PULL
    elif source.source_type == SourceType.SFTP:
        selected = IngestionMethod.SFTP_PULL
    elif source.source_type == SourceType.SHAREPOINT:
        selected = IngestionMethod.ADF_BATCH
    elif source.source_type == SourceType.ADLS and source.ingestion_frequency.upper() in {
        "CONTINUOUS",
        "HOURLY",
    }:
        selected = IngestionMethod.DATABRICKS_AUTO_LOADER
    elif source.source_type in {SourceType.ADLS, SourceType.MOCK}:
        selected = IngestionMethod.DATABRICKS_CONNECTOR_BATCH
    else:
        selected = IngestionMethod.MANUAL_CONTROLLED_UPLOAD
    rationale = f"Selected {selected.value} from source type {source.source_type.value}, frequency {source.ingestion_frequency}, and estimated inventory {profile.estimated_file_count}."
    return {
        "selected_strategy": selected.value,
        "rationale": rationale,
        "alternatives_considered": [item.value for item in IngestionMethod if item != selected],
        "operational_prerequisites": [
            "approved connector",
            "least-privilege identity",
            "idempotent batch identity",
        ],
        "failure_and_retry_behaviour": "bounded retries then DLQ",
        "checkpoint_or_watermark_strategy": "checkpoint"
        if selected == IngestionMethod.DATABRICKS_AUTO_LOADER
        else "batch identity",
        "configuration_gaps": [],
    }
