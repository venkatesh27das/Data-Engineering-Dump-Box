"""Metadata recommendations with explicit provenance."""

from source_readiness_agent.models.contracts import MetadataProfile, SourceDefinition


def generate_metadata_profile(
    source: SourceDefinition, additional_requirements: list[str] | None = None
) -> MetadataProfile:
    source_fields = [
        "source_system",
        "source_location",
        "source_owner",
        "ingestion_method",
        "batch_id",
        "ingested_at",
    ]
    document_fields = [
        "file_name",
        "mime_type",
        "size_bytes",
        "sha256",
        "source_path",
        "last_modified_at",
    ]
    for field in additional_requirements or []:
        if field not in document_fields:
            document_fields.append(field)
    return MetadataProfile(
        mandatory_source_fields=source_fields,
        mandatory_document_fields=document_fields,
        inferred_fields=["document_type", "business_domain", "region", "lifecycle_status"],
        static_tags={"source_id": source.source_id, "business_owner": source.business_owner},
        source_metadata_mapping={
            "file_name": "name",
            "last_modified_at": "last_modified",
            "source_path": "path",
        },
        completeness_threshold=0.9,
        provenance={
            "source_system": "source-provided",
            "file_name": "deterministically-derived",
            "document_type": "AI-inferred-requires-confirmation",
            "business_owner": "human-confirmed",
        },
    )
