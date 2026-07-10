from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FailureCategory(StrEnum):
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CORRUPT_FILE = "CORRUPT_FILE"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    PARSER_TIMEOUT = "PARSER_TIMEOUT"
    PARSER_RATE_LIMIT = "PARSER_RATE_LIMIT"
    PARSER_SERVICE_ERROR = "PARSER_SERVICE_ERROR"
    PARSER_CONFIGURATION_ERROR = "PARSER_CONFIGURATION_ERROR"
    PARTIAL_PARSE = "PARTIAL_PARSE"
    PAGE_COVERAGE_FAILURE = "PAGE_COVERAGE_FAILURE"
    OCR_QUALITY_FAILURE = "OCR_QUALITY_FAILURE"
    LAYOUT_EXTRACTION_FAILURE = "LAYOUT_EXTRACTION_FAILURE"
    TABLE_EXTRACTION_FAILURE = "TABLE_EXTRACTION_FAILURE"
    SCHEMA_VALIDATION_FAILURE = "SCHEMA_VALIDATION_FAILURE"
    METADATA_INCOMPLETE = "METADATA_INCOMPLETE"
    SOURCE_REFERENCE_MISSING = "SOURCE_REFERENCE_MISSING"
    CONFIDENCE_DISAGREEMENT = "CONFIDENCE_DISAGREEMENT"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class Diagnosis(BaseModel):
    primary_failure: FailureCategory
    contributing_failures: list[FailureCategory] = Field(default_factory=list)
    severity: str
    retryable: bool
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    eligible_strategies: list[str] = Field(default_factory=list)
    escalation_required: bool = False
    confidence: float = Field(default=0.8, ge=0, le=1)
