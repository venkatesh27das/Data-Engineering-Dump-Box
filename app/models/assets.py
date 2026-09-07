from typing import Any

from pydantic import BaseModel, Field


class Reference(BaseModel):
    sheet: str
    address: str
    kind: str
    external: bool = False


class FormulaAsset(BaseModel):
    formula_id: str
    workbook_id: str
    sheet_id: str
    cell: str
    formula: str
    cached_value: Any = None
    referenced_cells: list[str] = Field(default_factory=list)
    referenced_ranges: list[str] = Field(default_factory=list)
    referenced_sheets: list[str] = Field(default_factory=list)
    named_references: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    external_reference: bool = False
    parse_status: str = "parsed"
    issues: list[str] = Field(default_factory=list)


class TableAsset(BaseModel):
    table_id: str
    workbook_id: str
    sheet_id: str
    region_id: str
    table_name: str
    source_range: str
    columns: list[str]
    original_columns: list[str]
    row_count: int
    source_rows: list[int]
    parquet_path: str
    duckdb_table: str
    quality_score: float | None = None
    warnings: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    metadata: dict[str, Any] = Field(default_factory=dict)
