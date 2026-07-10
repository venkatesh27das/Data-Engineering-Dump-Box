from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class BronzeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    bronze_manifest_id: str
    source_file_uri: str
    source_system: str = "unknown"
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int = Field(ge=0)
    file_hash: str
    ingestion_batch_id: str | None = None
    processing_status: str = "INGESTED"
    current_run_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ParserRun(BaseModel):
    run_id: str
    document_id: str
    parser_id: str
    parser_version: str = "unknown"
    parser_config: dict[str, Any] = Field(default_factory=dict)
    model_endpoint: str | None = None
    prompt_version: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    status: str
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class SilverDocument(BaseModel):
    document_id: str
    run_id: str
    normalized_text: str = ""
    page_count: int = Field(default=0, ge=0)
    extracted_page_count: int = Field(default=0, ge=0)
    layout_payload: dict[str, Any] = Field(default_factory=dict)
    table_payload: list[dict[str, Any]] = Field(default_factory=list)
    figure_payload: list[dict[str, Any]] = Field(default_factory=list)
    parser_metadata: dict[str, Any] = Field(default_factory=dict)
    source_references: list[str] = Field(default_factory=list)
    parser_confidence: float | None = None
    created_at: datetime = Field(default_factory=utc_now)


class SilverElement(BaseModel):
    document_id: str
    run_id: str
    page_number: int = Field(ge=1)
    element_id: str
    element_type: str
    text: str = ""
    bounding_box: list[float] = Field(default_factory=list)
    confidence: float | None = None
    source_reference: str | None = None


class DocumentContext(BaseModel):
    manifest: BronzeManifest
    parser_run: ParserRun | None = None
    silver_document: SilverDocument | None = None
    silver_elements: list[SilverElement] = Field(default_factory=list)
    document_class: str = "unknown"
