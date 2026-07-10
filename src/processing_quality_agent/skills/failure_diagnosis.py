from __future__ import annotations

from dataclasses import dataclass

from processing_quality_agent.models.diagnosis import Diagnosis, FailureCategory
from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import QualityAssessment


@dataclass(frozen=True)
class FailureDefinition:
    severity: str
    retryable: bool
    strategies: tuple[str, ...]
    escalation_required: bool
    explanation: str


FAILURE_TAXONOMY: dict[FailureCategory, FailureDefinition] = {
    FailureCategory.UNSUPPORTED_FORMAT: FailureDefinition(
        "HIGH",
        False,
        ("REJECT_UNSUPPORTED",),
        False,
        "The file type is not supported by the configured parsers.",
    ),
    FailureCategory.CORRUPT_FILE: FailureDefinition(
        "CRITICAL",
        False,
        ("QUARANTINE",),
        True,
        "The source appears corrupt and cannot be safely parsed.",
    ),
    FailureCategory.PARSER_TIMEOUT: FailureDefinition(
        "MEDIUM",
        True,
        ("RETRY_SAME_CONFIGURATION", "RETRY_WITH_ALTERNATE_PARSER"),
        False,
        "The parser exceeded its configured timeout.",
    ),
    FailureCategory.PAGE_COVERAGE_FAILURE: FailureDefinition(
        "HIGH",
        True,
        ("PAGE_RANGE_REPROCESS", "RETRY_WITH_ALTERNATE_PARSER"),
        False,
        "Not all required pages were extracted.",
    ),
    FailureCategory.OCR_QUALITY_FAILURE: FailureDefinition(
        "HIGH",
        True,
        ("OCR_ENHANCED_REPROCESS", "RETRY_WITH_ALTERNATE_PARSER"),
        False,
        "OCR output is incomplete or unreadable.",
    ),
    FailureCategory.TABLE_EXTRACTION_FAILURE: FailureDefinition(
        "HIGH",
        True,
        ("TABLE_FOCUSED_REPROCESS", "RETRY_WITH_ALTERNATE_PARSER"),
        False,
        "Required table structure was not extracted.",
    ),
    FailureCategory.SCHEMA_VALIDATION_FAILURE: FailureDefinition(
        "HIGH",
        True,
        ("RETRY_WITH_CONFIGURATION_CHANGE",),
        True,
        "Parser output did not satisfy the normalized schema.",
    ),
    FailureCategory.METADATA_INCOMPLETE: FailureDefinition(
        "MEDIUM",
        True,
        ("RETRY_WITH_CONFIGURATION_CHANGE", "SEND_TO_HUMAN_REVIEW"),
        False,
        "Mandatory lineage metadata is incomplete.",
    ),
    FailureCategory.SOURCE_REFERENCE_MISSING: FailureDefinition(
        "HIGH",
        True,
        ("RETRY_WITH_CONFIGURATION_CHANGE",),
        True,
        "Output lacks source references required for traceability.",
    ),
    FailureCategory.CONFIDENCE_DISAGREEMENT: FailureDefinition(
        "MEDIUM",
        True,
        ("RETRY_WITH_ALTERNATE_PARSER", "SEND_TO_HUMAN_REVIEW"),
        False,
        "Parser confidence conflicts with deterministic quality evidence.",
    ),
    FailureCategory.PARTIAL_PARSE: FailureDefinition(
        "HIGH",
        True,
        ("RETRY_SAME_CONFIGURATION", "RETRY_WITH_ALTERNATE_PARSER"),
        False,
        "The parser returned only a partial result.",
    ),
    FailureCategory.EMPTY_DOCUMENT: FailureDefinition(
        "HIGH", False, ("SEND_TO_HUMAN_REVIEW", "QUARANTINE"), True, "No usable content was found."
    ),
    FailureCategory.UNKNOWN_FAILURE: FailureDefinition(
        "HIGH",
        False,
        ("SEND_TO_HUMAN_REVIEW",),
        True,
        "The evidence is insufficient to classify the failure safely.",
    ),
}


def definition(category: FailureCategory) -> FailureDefinition:
    return FAILURE_TAXONOMY.get(
        category,
        FailureDefinition(
            "HIGH",
            False,
            ("SEND_TO_HUMAN_REVIEW",),
            True,
            f"Failure classified as {category.value}.",
        ),
    )


def diagnose(context: DocumentContext, assessment: QualityAssessment) -> Diagnosis:
    run = context.parser_run
    flags = set(assessment.issue_flags) | set(assessment.hard_failures)
    if run and run.error_code:
        try:
            primary = FailureCategory(run.error_code)
        except ValueError:
            primary = FailureCategory.UNKNOWN_FAILURE
    elif "UNSUPPORTED_FORMAT" in flags:
        primary = FailureCategory.UNSUPPORTED_FORMAT
    elif assessment.metrics.page_coverage < 1:
        primary = FailureCategory.PAGE_COVERAGE_FAILURE
    elif (
        context.manifest.source_metadata.get("tables_expected")
        and assessment.metrics.table_quality < 0.5
    ):
        primary = FailureCategory.TABLE_EXTRACTION_FAILURE
    elif assessment.metrics.text_quality < 0.3:
        primary = FailureCategory.OCR_QUALITY_FAILURE
    elif assessment.metrics.schema_validity < 1:
        primary = FailureCategory.SCHEMA_VALIDATION_FAILURE
    elif (
        abs(assessment.metrics.normalized_parser_confidence - assessment.final_quality_score)
        >= 0.25
    ):
        primary = FailureCategory.CONFIDENCE_DISAGREEMENT
    else:
        primary = FailureCategory.UNKNOWN_FAILURE
    spec = definition(primary)
    return Diagnosis(
        primary_failure=primary,
        severity=spec.severity,
        retryable=spec.retryable,
        explanation=spec.explanation,
        evidence=[item for evidence in assessment.evidence for item in evidence.observations],
        eligible_strategies=list(spec.strategies),
        escalation_required=spec.escalation_required,
    )
