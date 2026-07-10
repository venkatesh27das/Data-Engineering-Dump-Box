import pytest

from processing_quality_agent.models.recovery import ApprovalContext
from processing_quality_agent.orchestration.policies import idempotency_key, reject_arbitrary_sql
from processing_quality_agent.orchestration.state import OperationState, WorkflowState
from processing_quality_agent.tools.base import (
    ApprovalRequiredError,
    UnsafeSourceURIError,
    WriteContext,
)
from processing_quality_agent.tools.volume_reader import VolumeReader


def test_approval_enforcement():
    with pytest.raises(ApprovalRequiredError):
        WriteContext(
            actor="a", approval=ApprovalContext(), reason="r", correlation_id="c"
        ).validate()


def test_idempotency_is_canonical():
    first = idempotency_key("x", "d", "r", "p", {"a": 1, "b": 2})
    second = idempotency_key("x", "d", "r", "p", {"b": 2, "a": 1})
    assert first == second


def test_state_transition_rejects_bypass():
    state = OperationState(correlation_id="c")
    with pytest.raises(ValueError):
        state.transition(WorkflowState.EXECUTING_RECOVERY)


@pytest.mark.parametrize("uri", ["/etc/passwd", "/Volumes/a/../secret", "file:///tmp/x"])
def test_source_uri_security(uri):
    with pytest.raises(UnsafeSourceURIError):
        VolumeReader(["/Volumes/"]).validate_uri(uri)


def test_arbitrary_sql_rejected():
    with pytest.raises(PermissionError):
        reject_arbitrary_sql("DROP TABLE anything")
