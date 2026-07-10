from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class WorkflowState(StrEnum):
    RECEIVED = "RECEIVED"
    CONTEXT_LOADED = "CONTEXT_LOADED"
    VALIDATING = "VALIDATING"
    AI_JUDGE_REQUIRED = "AI_JUDGE_REQUIRED"
    DIAGNOSING = "DIAGNOSING"
    PLAN_GENERATED = "PLAN_GENERATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING_RECOVERY = "EXECUTING_RECOVERY"
    VERIFYING_RECOVERY = "VERIFYING_RECOVERY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.RECEIVED: {WorkflowState.CONTEXT_LOADED, WorkflowState.FAILED},
    WorkflowState.CONTEXT_LOADED: {WorkflowState.VALIDATING, WorkflowState.FAILED},
    WorkflowState.VALIDATING: {
        WorkflowState.AI_JUDGE_REQUIRED,
        WorkflowState.DIAGNOSING,
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
    },
    WorkflowState.AI_JUDGE_REQUIRED: {WorkflowState.DIAGNOSING, WorkflowState.FAILED},
    WorkflowState.DIAGNOSING: {
        WorkflowState.PLAN_GENERATED,
        WorkflowState.COMPLETED,
        WorkflowState.ESCALATED,
        WorkflowState.FAILED,
    },
    WorkflowState.PLAN_GENERATED: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.EXECUTING_RECOVERY,
        WorkflowState.COMPLETED,
    },
    WorkflowState.AWAITING_APPROVAL: {WorkflowState.EXECUTING_RECOVERY, WorkflowState.COMPLETED},
    WorkflowState.EXECUTING_RECOVERY: {WorkflowState.VERIFYING_RECOVERY, WorkflowState.FAILED},
    WorkflowState.VERIFYING_RECOVERY: {
        WorkflowState.COMPLETED,
        WorkflowState.ESCALATED,
        WorkflowState.FAILED,
    },
    WorkflowState.ESCALATED: {WorkflowState.COMPLETED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
}


class OperationState(BaseModel):
    correlation_id: str
    current: WorkflowState = WorkflowState.RECEIVED
    history: list[WorkflowState] = Field(default_factory=lambda: [WorkflowState.RECEIVED])
    invoked_tools: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    def transition(self, target: WorkflowState) -> None:
        if target not in ALLOWED_TRANSITIONS[self.current]:
            raise ValueError(f"invalid transition {self.current} -> {target}")
        self.current = target
        self.history.append(target)
