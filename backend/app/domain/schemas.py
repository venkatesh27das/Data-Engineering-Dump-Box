from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal[
    "queued",
    "profiling",
    "planning",
    "extracting",
    "interpreting",
    "validating",
    "packaging",
    "needs_review",
    "completed",
    "failed",
    "cancelled",
]


class WorkbookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    display_name: str
    file_type: str
    file_size_bytes: int
    purpose: str
    description: str
    created_at: datetime
    updated_at: datetime
    latest_run_id: str | None = None
    latest_status: RunStatus = "queued"
    latest_confidence: float | None = None
    is_archived: bool = False


class RunOut(BaseModel):
    id: str
    workbook_id: str
    workbook_name: str
    purpose: str
    parent_run_id: str | None = None
    run_number: int
    trigger_type: str
    scope: str
    status: RunStatus
    current_stage: str
    progress_percent: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    overall_confidence: float | None = None
    output_unit_count: int | None = None
    error_message: str | None = None


class AssetOut(BaseModel):
    id: str
    asset_type: str
    title: str
    summary: str
    source_sheet: str | None = None
    source_range: str | None = None
    confidence: float
    review_status: str


class ReviewItemOut(BaseModel):
    id: str
    title: str
    description: str
    evidence: str
    suggested_action: str
    confidence: float
    severity: str
    status: str


class FeedbackRequest(BaseModel):
    raw_text: str = Field(min_length=2, max_length=10_000)
    scope: str = "impacted_assets"
    preserve_approved_assets: bool = True


class Directive(BaseModel):
    directive_id: str
    type: str
    target: dict[str, Any]
    parameters: dict[str, Any]
    confidence: float
    requires_confirmation: bool = False


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    timestamp: datetime
    stage: str
    status: str
    progress_percent: int
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CanonicalContentUnit(BaseModel):
    unit_id: str
    unit_type: str
    title: str
    text_content: str
    structured_content: dict[str, Any]
    semantic_context: dict[str, Any]
    structural_context: dict[str, Any]
    media_references: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any]
    quality: dict[str, Any]
    embedding_status: str = "ready"
    entity_extraction_status: str = "ready"
