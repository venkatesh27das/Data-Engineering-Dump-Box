from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .document import utc_now


class QualityDecision(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    RETRY_SAME_PARSER = "RETRY_SAME_PARSER"
    RETRY_ALTERNATE_PARSER = "RETRY_ALTERNATE_PARSER"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    QUARANTINE = "QUARANTINE"
    REJECT_UNSUPPORTED = "REJECT_UNSUPPORTED"


class MetricEvidence(BaseModel):
    metric: str
    score: float = Field(ge=0, le=1)
    observations: list[str] = Field(default_factory=list)


class QualityMetrics(BaseModel):
    schema_validity: float = Field(ge=0, le=1)
    page_coverage: float = Field(ge=0, le=1)
    text_quality: float = Field(ge=0, le=1)
    layout_quality: float = Field(ge=0, le=1)
    table_quality: float = Field(ge=0, le=1)
    metadata_completeness: float = Field(ge=0, le=1)
    source_reference_completeness: float = Field(ge=0, le=1)
    normalized_parser_confidence: float = Field(ge=0, le=1)
    ai_judge_score: float | None = Field(default=None, ge=0, le=1)


class AIJudgeResult(BaseModel):
    score: float = Field(ge=0, le=1)
    decision: str
    issues: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    explanation: str
    uncertainty: str
    recommended_action: str


class QualityAssessment(BaseModel):
    assessment_id: str
    document_id: str
    run_id: str
    metrics: QualityMetrics
    final_quality_score: float = Field(ge=0, le=1)
    issue_flags: list[str] = Field(default_factory=list)
    decision: QualityDecision
    explanation: str
    evidence: list[MetricEvidence] = Field(default_factory=list)
    hard_failures: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class QualityPolicy(BaseModel):
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "schema_validity": 0.15,
            "page_coverage": 0.15,
            "text_quality": 0.15,
            "layout_quality": 0.10,
            "table_quality": 0.10,
            "metadata_completeness": 0.10,
            "source_reference_completeness": 0.10,
            "normalized_parser_confidence": 0.10,
            "ai_judge_score": 0.05,
        }
    )
    publish_threshold: float = Field(default=0.85, ge=0, le=1)
    warning_threshold: float = Field(default=0.75, ge=0, le=1)
    human_review_threshold: float = Field(default=0.60, ge=0, le=1)
    ai_judge_margin: float = Field(default=0.05, ge=0, le=0.25)
    confidence_disagreement_threshold: float = Field(default=0.25, ge=0, le=1)
    blocking_failures: set[str] = Field(
        default_factory=lambda: {"CORRUPT_FILE", "UNSUPPORTED_FORMAT", "SCHEMA_VALIDATION_FAILURE"}
    )
    high_risk_classes: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_weights(self) -> QualityPolicy:
        if not self.weights or any(value < 0 for value in self.weights.values()):
            raise ValueError("quality weights must be non-negative")
        if sum(self.weights.values()) <= 0:
            raise ValueError("quality weights must have a positive sum")
        return self
