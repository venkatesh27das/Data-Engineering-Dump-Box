from typing import Literal

from pydantic import BaseModel, Field


class ForeignKeyDefinition(BaseModel):
    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]
    constraint_name: str | None = None
    inferred: bool = False


class ColumnDefinition(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    inferred_key: bool = False
    references_table: str | None = None
    references_column: str | None = None
    description: str | None = None


class TableDefinition(BaseModel):
    name: str
    columns: list[ColumnDefinition]
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyDefinition] = Field(default_factory=list)
    description: str | None = None


class DocumentPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str
    character_count: int = Field(ge=0)


class DocumentChunk(BaseModel):
    id: str
    text: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)


class NormalizedSource(BaseModel):
    source_id: str
    source_name: str
    modality: Literal["structured", "unstructured"]
    source_type: str
    text: str = ""
    tables: list[TableDefinition] = Field(default_factory=list)
    pages: list[DocumentPage] = Field(default_factory=list)
    chunks: list[DocumentChunk] = Field(default_factory=list)
    parsing_confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
