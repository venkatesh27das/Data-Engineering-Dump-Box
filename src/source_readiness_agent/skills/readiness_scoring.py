"""Configurable deterministic scoring with blocking-condition overrides."""

from __future__ import annotations

from uuid import uuid4

from source_readiness_agent.models.contracts import (
    Evidence,
    ReadinessAssessment,
    ReadinessStatus,
    SourceProfile,
)

DEFAULT_WEIGHTS = {
    "connectivity_and_permissions": 0.15,
    "file_format_compatibility": 0.10,
    "file_integrity": 0.10,
    "metadata_completeness": 0.10,
    "inventory_quality": 0.05,
    "landing_path_readiness": 0.10,
    "checkpoint_readiness": 0.05,
    "bronze_registration_readiness": 0.10,
    "parser_eligibility": 0.10,
    "workflow_readiness": 0.05,
    "governance_readiness": 0.05,
    "sample_run_result": 0.05,
}


def score_readiness(
    profile: SourceProfile,
    configured: bool = False,
    weights: dict[str, float] | None = None,
    sample_score: float | None = None,
) -> ReadinessAssessment:
    weights = weights or DEFAULT_WEIGHTS
    if abs(sum(weights.values()) - 1.0) > 0.0001:
        raise ValueError("readiness weights must total 1.0")
    count = max(profile.sampled_file_count, 1)
    supported_ratio = (count - profile.unsupported_file_count) / count
    integrity = (count - profile.zero_byte_count - profile.corrupt_candidate_count) / count
    category = {
        "connectivity_and_permissions": 100.0
        if profile.access_validation.accessible and profile.access_validation.allowed
        else 0.0,
        "file_format_compatibility": max(0, supported_ratio * 100),
        "file_integrity": max(0, integrity * 100),
        "metadata_completeness": profile.metadata_completeness * 100,
        "inventory_quality": 100.0 if profile.estimated_file_count > 0 else 0.0,
        "landing_path_readiness": 100.0 if configured else 50.0,
        "checkpoint_readiness": 100.0 if configured else 50.0,
        "bronze_registration_readiness": 100.0 if configured else 50.0,
        "parser_eligibility": supported_ratio * 100,
        "workflow_readiness": 100.0 if configured else 50.0,
        "governance_readiness": 100.0 if profile.access_validation.allowed else 0.0,
        "sample_run_result": sample_score if sample_score is not None else 50.0,
    }
    blocking: list[str] = []
    status: ReadinessStatus
    if not profile.access_validation.allowed:
        blocking.append("SOURCE_OUTSIDE_ALLOWLIST")
        status = ReadinessStatus.ACCESS_BLOCKED
    elif not profile.access_validation.accessible:
        blocking.append("SOURCE_INACCESSIBLE")
        status = ReadinessStatus.ACCESS_BLOCKED
    elif profile.sampled_file_count == 0 or supported_ratio <= 0:
        blocking.append("NO_SUPPORTED_FILES_FOUND")
        status = ReadinessStatus.NOT_READY
    elif sample_score is not None and sample_score < 90:
        blocking.append("SAMPLE_RUN_FAILED_THRESHOLD")
        status = ReadinessStatus.SAMPLE_RUN_FAILED
    elif not configured:
        status = ReadinessStatus.CONFIGURATION_REQUIRED
    else:
        status = ReadinessStatus.READY
    score = round(sum(category[key] * weight for key, weight in weights.items()), 2)
    warnings = list(profile.issues)
    if profile.unsupported_file_count:
        warnings.append(f"{profile.unsupported_file_count} sampled files are unsupported")
    if not blocking and warnings:
        status = ReadinessStatus.READY_WITH_WARNINGS if configured else status
    actions = [f"Remediate {issue}" for issue in blocking]
    if not configured:
        actions.append("Generate and validate a source configuration proposal")
    evidence = [
        Evidence(category=key, message=f"deterministic category score={value:.2f}")
        for key, value in category.items()
    ]
    return ReadinessAssessment(
        assessment_id=f"ASSESS-{uuid4().hex[:12].upper()}",
        source_id=profile.source_id,
        readiness_score=score,
        readiness_status=status,
        category_scores=category,
        blocking_issues=blocking,
        warnings=warnings,
        recommended_actions=actions,
        evidence=evidence,
        source_profile=profile,
    )
