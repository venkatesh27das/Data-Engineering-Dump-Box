"""Aggregate bounded file profiles into a source profile."""

from collections import Counter

from source_readiness_agent.models.contracts import (
    ConnectionValidationResult,
    FileProfile,
    SourceInventoryEstimate,
    SourceProfile,
)


def build_source_profile(
    source_id: str,
    inventory: SourceInventoryEstimate,
    access: ConnectionValidationResult,
    profiles: list[FileProfile],
) -> SourceProfile:
    hashes: Counter[str] = Counter()
    for profile in profiles:
        hashes[profile.file_name.lower()] += 1
    for profile in profiles:
        profile.duplicate_candidate = hashes[profile.file_name.lower()] > 1
    count = len(profiles)
    sizes = {"small": 0, "medium": 0, "large": 0}
    for profile in profiles:
        sizes[
            "small"
            if profile.size_bytes < 1_048_576
            else "medium"
            if profile.size_bytes < 10_485_760
            else "large"
        ] += 1
    issues = list(access.issues)
    if not profiles:
        issues.append("NO_FILES_SAMPLED")
    return SourceProfile(
        source_id=source_id,
        estimated_file_count=inventory.estimated_file_count,
        estimated_total_bytes=inventory.estimated_total_bytes,
        sampled_file_count=count,
        file_type_distribution=dict(Counter(p.file_type for p in profiles)),
        modality_distribution=dict(Counter(p.modality.value for p in profiles)),
        size_distribution=sizes,
        unsupported_file_count=sum(not p.supported for p in profiles),
        zero_byte_count=sum(p.zero_byte for p in profiles),
        corrupt_candidate_count=sum(p.corrupt_signal for p in profiles),
        duplicate_candidate_count=sum(p.duplicate_candidate for p in profiles),
        complex_document_ratio=sum(p.layout_complexity >= 0.7 for p in profiles) / count
        if count
        else 0,
        scanned_document_ratio=sum(p.scanned_probability >= 0.7 for p in profiles) / count
        if count
        else 0,
        metadata_completeness=sum(p.metadata_completeness for p in profiles) / count
        if count
        else 0,
        access_validation=access,
        file_profiles=profiles,
        issues=issues,
    )
