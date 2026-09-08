from typing import Any, Literal

from pydantic import BaseModel, Field

RegionType = Literal[
    "title",
    "header",
    "table",
    "summary_table",
    "kpi_block",
    "narrative",
    "notes",
    "image",
    "chart",
    "empty",
    "unknown",
]


class Region(BaseModel):
    region_id: str
    sheet_id: str
    range: str
    region_type: RegionType = "table"
    confidence: float = Field(default=1.0, ge=0, le=1)
    detected_by: str = "native_excel_table"
    requires_agent_review: bool = False
    agent_review_status: str = "not_requested"
    header_row: int | None = None
    features: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    agent_result: dict[str, Any] | None = None
