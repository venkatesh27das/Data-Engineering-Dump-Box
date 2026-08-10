from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PublicationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PublicationResult(BaseModel):
    nodes_published: int = Field(ge=0)
    relationships_published: int = Field(ge=0)
    assets_skipped: int = Field(ge=0)


class Publication(BaseModel):
    id: str
    project_id: str
    package_id: str
    status: PublicationStatus
    nodes_published: int = Field(default=0, ge=0)
    relationships_published: int = Field(default=0, ge=0)
    assets_skipped: int = Field(default=0, ge=0)
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PublicationStatusResponse(BaseModel):
    configured: bool
    connected: bool
    latest: Publication | None = None
    history: list[Publication] = Field(default_factory=list)
