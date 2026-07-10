"""Resumable operation state and deterministic transitions."""

from enum import StrEnum

from pydantic import Field

from source_readiness_agent.models.contracts import StrictModel


class WorkflowState(StrEnum):
    RECEIVED = "RECEIVED"
    SOURCE_VALIDATING = "SOURCE_VALIDATING"
    SOURCE_CONNECTED = "SOURCE_CONNECTED"
    INVENTORY_ESTIMATING = "INVENTORY_ESTIMATING"
    SAMPLE_SELECTING = "SAMPLE_SELECTING"
    FILES_PROFILING = "FILES_PROFILING"
    READINESS_SCORING = "READINESS_SCORING"
    CONFIGURATION_GENERATING = "CONFIGURATION_GENERATING"
    CONFIGURATION_VALIDATING = "CONFIGURATION_VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SAMPLE_RUN_EXECUTING = "SAMPLE_RUN_EXECUTING"
    SAMPLE_RUN_VALIDATING = "SAMPLE_RUN_VALIDATING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"
    ACTIVATION_AWAITING_APPROVAL = "ACTIVATION_AWAITING_APPROVAL"
    ACTIVATED = "ACTIVATED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


TRANSITIONS = {
    WorkflowState.RECEIVED: {
        WorkflowState.SOURCE_VALIDATING,
        WorkflowState.CONFIGURATION_GENERATING,
        WorkflowState.CONFIGURATION_VALIDATING,
        WorkflowState.SAMPLE_RUN_EXECUTING,
        WorkflowState.ACTIVATION_AWAITING_APPROVAL,
    },
    WorkflowState.SOURCE_VALIDATING: {
        WorkflowState.SOURCE_CONNECTED,
        WorkflowState.NOT_READY,
        WorkflowState.FAILED,
    },
    WorkflowState.SOURCE_CONNECTED: {WorkflowState.INVENTORY_ESTIMATING},
    WorkflowState.INVENTORY_ESTIMATING: {WorkflowState.SAMPLE_SELECTING},
    WorkflowState.SAMPLE_SELECTING: {WorkflowState.FILES_PROFILING},
    WorkflowState.FILES_PROFILING: {WorkflowState.READINESS_SCORING},
    WorkflowState.READINESS_SCORING: {
        WorkflowState.READY,
        WorkflowState.READY_WITH_WARNINGS,
        WorkflowState.NOT_READY,
        WorkflowState.AWAITING_APPROVAL,
    },
    WorkflowState.CONFIGURATION_GENERATING: {
        WorkflowState.CONFIGURATION_VALIDATING,
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.FAILED,
    },
    WorkflowState.CONFIGURATION_VALIDATING: {
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.NOT_READY,
        WorkflowState.FAILED,
    },
    WorkflowState.AWAITING_APPROVAL: {
        WorkflowState.SAMPLE_RUN_EXECUTING,
        WorkflowState.ACTIVATION_AWAITING_APPROVAL,
    },
    WorkflowState.SAMPLE_RUN_EXECUTING: {WorkflowState.SAMPLE_RUN_VALIDATING, WorkflowState.FAILED},
    WorkflowState.SAMPLE_RUN_VALIDATING: {
        WorkflowState.READY,
        WorkflowState.READY_WITH_WARNINGS,
        WorkflowState.NOT_READY,
    },
    WorkflowState.ACTIVATION_AWAITING_APPROVAL: {WorkflowState.ACTIVATED, WorkflowState.FAILED},
}


class OperationState(StrictModel):
    correlation_id: str
    source_id: str | None = None
    assessment_id: str | None = None
    proposal_id: str | None = None
    sample_run_id: str | None = None
    actor: str
    current_state: WorkflowState = WorkflowState.RECEIVED
    evidence: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    approval_state: str = "NOT_REQUIRED"
    operation_history: list[WorkflowState] = Field(default_factory=lambda: [WorkflowState.RECEIVED])

    def transition(self, target: WorkflowState) -> None:
        if target not in TRANSITIONS.get(self.current_state, set()):
            raise ValueError(f"invalid state transition: {self.current_state} -> {target}")
        self.current_state = target
        self.operation_history.append(target)
