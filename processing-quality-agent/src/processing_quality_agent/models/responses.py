from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .diagnosis import Diagnosis
from .document import DocumentContext, utc_now
from .quality import QualityAssessment
from .recovery import RecoveryAttempt, RecoveryPlan
from .requests import OperationMode


class ParserScore(BaseModel):
    parser_id: str
    overall_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    success_score: float = Field(ge=0, le=1)
    latency_score: float = Field(ge=0, le=1)
    cost_score: float = Field(ge=0, le=1)
    stability_score: float = Field(ge=0, le=1)
    rationale: str


class ParserComparison(BaseModel):
    rankings: list[ParserScore]
    recommended_parser_id: str | None = None
    profile: str
    warnings: list[str] = Field(default_factory=list)


class AuditMetadata(BaseModel):
    actor: str
    correlation_id: str
    invoked_tools: list[str] = Field(default_factory=list)
    state_history: list[str] = Field(default_factory=list)
    environment: str
    created_at: datetime = Field(default_factory=utc_now)


class AgentOperationResponse(BaseModel):
    correlation_id: str
    operation_mode: OperationMode
    document_context: DocumentContext | None = None
    diagnosis: Diagnosis | None = None
    evidence: list[str] = Field(default_factory=list)
    quality_assessment: QualityAssessment | None = None
    parser_comparison: ParserComparison | None = None
    recovery_plan: RecoveryPlan | None = None
    recovery_attempt: RecoveryAttempt | None = None
    proposed_policy_yaml: str | None = None
    recommended_action: str | None = None
    approval_required: bool = False
    execution_status: str = "COMPLETED"
    resulting_run_id: str | None = None
    final_decision: str | None = None
    warnings: list[str] = Field(default_factory=list)
    audit: AuditMetadata


class ResponsesAgentOutput(BaseModel):
    id: str
    object: str = "response"
    created_at: int
    status: str = "completed"
    output: list[dict[str, Any]]
    custom_outputs: dict[str, Any] = Field(default_factory=dict)
