from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.projects import SourceAsset


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class PlanStep(BaseModel):
    specialist: Literal["source_analyst", "knowledge_engineer", "graph_modeller", "quality_reviewer"]
    tool: str
    reason: str


class ExecutionPlan(BaseModel):
    source_modalities: list[Literal["structured", "unstructured"]]
    graph_levels: list[str]
    steps: list[PlanStep]
    plan_source: Literal["deep_agent", "deterministic_fallback"] = "deterministic_fallback"


class Run(BaseModel):
    id: str
    project_id: str
    status: RunStatus
    current_stage: str
    plan: ExecutionPlan | None = None
    package_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentEvent(BaseModel):
    id: str
    run_id: str
    sequence: int = Field(ge=1)
    timestamp: datetime
    stage: str
    status: Literal["queued", "running", "completed", "warning", "failed", "canceled"]
    title: str
    message: str
    event_type: Literal["stage", "tool", "replan", "quality", "run"]


class AssetPackageSummary(BaseModel):
    package_id: str
    project_id: str
    run_id: str
    entity_count: int
    relationship_count: int
    concept_count: int
    fact_count: int
    event_count: int
    quality_score: float = Field(ge=0, le=1)
    created_at: datetime


class RunArtifact(BaseModel):
    id: str
    run_id: str
    stage: str
    artifact_type: str
    name: str
    status: Literal["temporary", "completed", "failed"] = "completed"
    record_count: int = Field(default=0, ge=0)
    parent_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class RunQueueItem(BaseModel):
    run: Run
    project_name: str
    source_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    artifact_count: int = Field(ge=0)
    package: AssetPackageSummary | None = None


class RunLineageEdge(BaseModel):
    parent_id: str
    child_id: str
    relationship: str = "derived_into"


class RunDetail(BaseModel):
    item: RunQueueItem
    sources: list[SourceAsset]
    events: list[AgentEvent]
    temporary_assets: list[RunArtifact]
    lineage: list[RunLineageEdge]
