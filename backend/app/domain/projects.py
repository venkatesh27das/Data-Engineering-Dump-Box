from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProcessingMode(StrEnum):
    AUTO = "auto"
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"
    HYBRID = "hybrid"


class GraphDepth(StrEnum):
    METADATA = "metadata"
    ENTITY_RELATIONSHIPS = "entity_relationships"
    SEMANTIC = "semantic"
    CONTEXTUAL = "contextual"


class SourceCategory(StrEnum):
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    knowledge_objective: str = Field(min_length=1, max_length=2_000)
    processing_mode: ProcessingMode = ProcessingMode.AUTO
    graph_depth: GraphDepth = GraphDepth.ENTITY_RELATIONSHIPS
    review_low_confidence: bool = True
    max_tokens: int = Field(default=2048, ge=512, le=131_072)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    knowledge_objective: str | None = Field(default=None, min_length=1, max_length=2_000)
    processing_mode: ProcessingMode | None = None
    graph_depth: GraphDepth | None = None
    review_low_confidence: bool | None = None
    max_tokens: int | None = Field(default=None, ge=512, le=131_072)

    @model_validator(mode="after")
    def require_change(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one project field must be provided")
        return self


class Project(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class SourceAsset(BaseModel):
    id: str
    project_id: str
    filename: str
    original_filename: str
    category: SourceCategory
    extension: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    storage_path: str
    status: str = "uploaded"
    summary: str = "Ready for analysis"
    created_at: datetime
