import pytest

from processing_quality_agent.config import Settings
from processing_quality_agent.models.recovery import ApprovalContext, RecoveryStrategy
from processing_quality_agent.models.requests import (
    CompareParsersRequest,
    InvestigateRequest,
    OptimizePolicyRequest,
    RecoverRequest,
)
from processing_quality_agent.orchestration.workflow import AgentOrchestrator
from processing_quality_agent.tools.mock_repository import InMemoryRepository
from processing_quality_agent.tools.workflow_client import MockWorkflowClient


@pytest.fixture
def orchestrator():
    return AgentOrchestrator(
        Settings(use_mock_tools=True), InMemoryRepository(), MockWorkflowClient()
    )


async def test_investigate(orchestrator):
    result = await orchestrator.investigate(InvestigateRequest(document_id="DOC-102"))
    assert result.diagnosis.primary_failure.value == "TABLE_EXTRACTION_FAILURE"
    assert "get_document_context" in result.audit.invoked_tools


async def test_unapproved_recovery_is_blocked(orchestrator):
    result = await orchestrator.recover(
        RecoverRequest(document_id="DOC-102", source_run_id="RUN-101", dry_run=False)
    )
    assert result.execution_status == "AWAITING_APPROVAL"
    assert result.resulting_run_id is None


async def test_approved_recovery_executes(orchestrator):
    request = RecoverRequest(
        document_id="DOC-102",
        source_run_id="RUN-101",
        strategy=RecoveryStrategy.RETRY_WITH_ALTERNATE_PARSER,
        preferred_parser_id="azure_document_intelligence",
        approval=ApprovalContext(
            approved=True, approval_reference="CHG-1", approved_by="engineer@example.com"
        ),
        actor="engineer@example.com",
        dry_run=False,
    )
    result = await orchestrator.recover(request)
    assert result.execution_status == "SUCCEEDED"
    assert result.resulting_run_id.startswith("mock-run-")
    assert result.recovery_attempt.before_quality_score is not None
    assert result.recovery_attempt.after_quality_score is not None
    assert result.recovery_attempt.outcome == "IMPROVED"
    assert "create_recovery_attempt" in result.audit.invoked_tools
    assert "record_quality_assessment" in result.audit.invoked_tools
    assert "update_processing_status" in result.audit.invoked_tools
    assert result.document_context.parser_run.run_id == result.resulting_run_id


async def test_compare_two_parsers(orchestrator):
    result = await orchestrator.compare(
        CompareParsersRequest(
            document_id="DOC-102",
            parser_candidates=["databricks_primary", "azure_document_intelligence"],
        )
    )
    assert len(result.parser_comparison.rankings) == 2
    assert result.parser_comparison.recommended_parser_id == "azure_document_intelligence"


async def test_optimize_proposes_yaml_without_applying(orchestrator):
    result = await orchestrator.optimize(
        OptimizePolicyRequest(
            document_class="scanned_policy_pdf",
            allowed_parser_candidates=["databricks_primary", "azure_document_intelligence"],
        )
    )
    assert "primary_parser: azure_document_intelligence" in result.proposed_policy_yaml
    assert result.final_decision == "PROPOSED"
    assert result.approval_required


async def test_optimize_applies_approved_policy_idempotently(orchestrator):
    request = OptimizePolicyRequest(
        document_class="scanned_policy_pdf",
        allowed_parser_candidates=["databricks_primary", "azure_document_intelligence"],
        apply=True,
        approval=ApprovalContext(
            approved=True, approval_reference="CHG-2", approved_by="approver@example.com"
        ),
        actor="engineer@example.com",
        dry_run=False,
    )
    first = await orchestrator.optimize(request)
    second = await orchestrator.optimize(request)
    assert first.final_decision == "APPLIED"
    assert "apply_approved_routing_policy" in first.audit.invoked_tools
    assert second.final_decision == "APPLIED"
    policy_writes = [
        key
        for key in orchestrator.repository.operations
        if key.startswith("apply_approved_routing_policy:")
    ]
    assert len(policy_writes) == 1
