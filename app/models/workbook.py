from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.run import Stage, now


class Workbook(BaseModel):
    workbook_id: str
    run_id: str
    filename: str
    file_path: str
    file_hash: str
    file_size_bytes: int
    created_at: datetime = Field(default_factory=now)
    sheet_count: int = 0
    formula_count: int = 0
    table_count: int = 0
    image_count: int = 0
    chart_count: int = 0
    named_range_count: int = 0
    hidden_sheet_count: int = 0
    processing_status: Stage = Stage.UPLOADED
    overall_quality_score: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    named_ranges: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)


class Sheet(BaseModel):
    sheet_id: str
    workbook_id: str
    name: str
    index: int
    visibility: str
    max_row: int
    max_column: int
    non_empty_cells: int = 0
    formula_count: int = 0
    table_count: int = 0
    image_count: int = 0
    chart_count: int = 0
    merged_range_count: int = 0
    region_count: int = 0
    merged_ranges: list[str] = Field(default_factory=list)
    comments: list[dict[str, Any]] = Field(default_factory=list)
    hyperlinks: list[dict[str, Any]] = Field(default_factory=list)
    native_tables: list[dict[str, Any]] = Field(default_factory=list)
