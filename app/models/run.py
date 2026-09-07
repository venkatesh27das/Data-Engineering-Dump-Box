from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(UTC)


class Stage(StrEnum):
    UPLOADED = "UPLOADED"
    INSPECTING = "INSPECTING"
    EXTRACTING_TABLES = "EXTRACTING_TABLES"
    PARSING_FORMULAS = "PARSING_FORMULAS"
    BUILDING_GRAPH = "BUILDING_GRAPH"
    NORMALIZING = "NORMALIZING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"


class Run(BaseModel):
    run_id: str
    workbook_id: str
    stage: Stage = Stage.UPLOADED
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    error: str | None = None
    output_path: str | None = None


class WarningRecord(BaseModel):
    code: str
    message: str
    sheet_name: str | None = None
    cell: str | None = None
