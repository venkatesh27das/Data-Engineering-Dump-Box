from typing import Any, Literal

from pydantic import BaseModel, Field


class ProcessingPlan(BaseModel):
    workbook_archetype: str
    steps: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    reasoning_summary: str


class EntityCandidate(BaseModel):
    label: str
    entity_type: str
    evidence: str
    source_sheet: str | None = None
    source_range: str | None = None
    confidence: float = Field(ge=0, le=1)


class RelationshipCandidate(BaseModel):
    source: str
    relationship_type: str
    target: str
    evidence: str
    source_sheet: str | None = None
    source_range: str | None = None
    confidence: float = Field(ge=0, le=1)


class SemanticInterpretation(BaseModel):
    summary: str
    domain: str
    business_terms: list[str] = Field(default_factory=list)
    entities: list[EntityCandidate] = Field(default_factory=list)
    relationships: list[RelationshipCandidate] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class VisualInterpretation(BaseModel):
    description: str
    classification: str
    extracted_text: list[str] = Field(default_factory=list)
    related_asset: str | None = None
    confidence: float = Field(ge=0, le=1)


class OCRExtraction(BaseModel):
    full_text: str
    language: str | None = None
    confidence: float = Field(ge=0, le=1)


class ChartInterpretation(BaseModel):
    summary: str
    insights: list[str] = Field(default_factory=list)
    business_purpose: str
    confidence: float = Field(ge=0, le=1)


class ValidationSummary(BaseModel):
    status: Literal["passed", "review_recommended"]
    findings: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class FeedbackDirective(BaseModel):
    type: Literal[
        "override_header_row",
        "exclude_sheet",
        "confirm_semantic_mapping",
        "set_business_context",
    ]
    target: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    requires_confirmation: bool = False


class FeedbackInterpretation(BaseModel):
    directives: list[FeedbackDirective]
