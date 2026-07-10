from __future__ import annotations

from uuid import uuid4

from processing_quality_agent.config import Settings
from processing_quality_agent.models.recovery import RecoveryAttempt
from processing_quality_agent.models.requests import (
    CompareParsersRequest,
    InvestigateRequest,
    OperationMode,
    OptimizePolicyRequest,
    RecoverRequest,
)
from processing_quality_agent.models.responses import AgentOperationResponse, AuditMetadata
from processing_quality_agent.orchestration.approval import require_approval
from processing_quality_agent.orchestration.policies import idempotency_key
from processing_quality_agent.orchestration.state import OperationState, WorkflowState
from processing_quality_agent.services.comparison_service import ComparisonService
from processing_quality_agent.services.diagnosis_service import DiagnosisService
from processing_quality_agent.services.optimization_service import OptimizationService
from processing_quality_agent.services.quality_service import QualityService
from processing_quality_agent.services.recovery_service import RecoveryService
from processing_quality_agent.tools.mock_repository import InMemoryRepository
from processing_quality_agent.tools.workflow_client import DatabricksWorkflowClient
from processing_quality_agent.tracing import traced_operation


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        repository: InMemoryRepository,
        workflow_client: DatabricksWorkflowClient,
    ) -> None:
        self.settings, self.repository, self.workflow_client = settings, repository, workflow_client
        self.quality = QualityService()
        self.diagnosis = DiagnosisService()
        self.comparison = ComparisonService()
        self.recovery = RecoveryService(
            settings.maximum_automatic_retries_per_parser, settings.maximum_total_parser_attempts
        )
        self.optimization = OptimizationService()
        self.operations: dict[str, AgentOperationResponse] = {}

    def _ids(
        self, correlation_id: str | None, actor: str
    ) -> tuple[str, OperationState, AuditMetadata]:
        cid = correlation_id or str(uuid4())
        state = OperationState(correlation_id=cid)
        return (
            cid,
            state,
            AuditMetadata(actor=actor, correlation_id=cid, environment=self.settings.app_env),
        )

    @staticmethod
    def _sync_audit(state: OperationState, audit: AuditMetadata) -> None:
        audit.invoked_tools = state.invoked_tools
        audit.state_history = [item.value for item in state.history]

    @traced_operation("processing_quality.investigate")
    async def investigate(self, request: InvestigateRequest) -> AgentOperationResponse:
        cid, state, audit = self._ids(request.correlation_id, request.actor)
        if not request.document_id:
            raise ValueError(
                "batch/run-only investigation requires a configured repository resolver"
            )
        context = await self.repository.get_document_context(request.document_id, request.run_id)
        state.invoked_tools.append("get_document_context")
        state.transition(WorkflowState.CONTEXT_LOADED)
        state.transition(WorkflowState.VALIDATING)
        assessment = self.quality.evaluate(context)
        state.transition(WorkflowState.DIAGNOSING)
        diagnosis = self.diagnosis.diagnose(context, assessment)
        state.evidence.extend(diagnosis.evidence)
        state.transition(WorkflowState.COMPLETED)
        self._sync_audit(state, audit)
        response = AgentOperationResponse(
            correlation_id=cid,
            operation_mode=OperationMode.INVESTIGATE,
            document_context=context,
            diagnosis=diagnosis,
            evidence=diagnosis.evidence,
            quality_assessment=assessment,
            recommended_action=diagnosis.eligible_strategies[0]
            if diagnosis.eligible_strategies
            else "HUMAN_REVIEW",
            final_decision=assessment.decision.value,
            audit=audit,
        )
        self.operations[cid] = response
        return response

    @traced_operation("processing_quality.recover")
    async def recover(self, request: RecoverRequest) -> AgentOperationResponse:
        cid, state, audit = self._ids(request.correlation_id, request.actor)
        context = await self.repository.get_document_context(
            request.document_id, request.source_run_id
        )
        state.invoked_tools.append("get_document_context")
        state.transition(WorkflowState.CONTEXT_LOADED)
        state.transition(WorkflowState.VALIDATING)
        before = self.quality.evaluate(context)
        state.transition(WorkflowState.DIAGNOSING)
        diagnosis = self.diagnosis.diagnose(context, before)
        history = await self.repository.get_parser_history(request.document_id)
        state.invoked_tools.append("get_parser_history")
        plan = self.recovery.plan(diagnosis, history, request.strategy, request.preferred_parser_id)
        state.transition(WorkflowState.PLAN_GENERATED)
        parser_id = plan.parser_id or "databricks_primary"
        if not request.approval.valid() and not request.dry_run:
            state.transition(WorkflowState.AWAITING_APPROVAL)
            state.transition(WorkflowState.COMPLETED)
            self._sync_audit(state, audit)
            response = AgentOperationResponse(
                correlation_id=cid,
                operation_mode=OperationMode.RECOVER,
                document_context=context,
                diagnosis=diagnosis,
                quality_assessment=before,
                recovery_plan=plan,
                recommended_action=plan.strategy.value,
                approval_required=True,
                execution_status="AWAITING_APPROVAL",
                final_decision=before.decision.value,
                audit=audit,
            )
            self.operations[cid] = response
            return response
        if not request.dry_run:
            require_approval(request.approval)
        state.transition(WorkflowState.EXECUTING_RECOVERY)
        key = idempotency_key(
            "recover", request.document_id, request.source_run_id, parser_id, request.parser_config
        )
        run = await self.workflow_client.trigger_parser_run(
            document_id=request.document_id,
            source_file_uri=context.manifest.source_file_uri,
            parser_id=parser_id,
            parser_config=request.parser_config,
            source_run_id=request.source_run_id,
            recovery_id=f"recovery-{cid}",
            idempotency_key=key,
            dry_run=request.dry_run,
        )
        state.invoked_tools.append("trigger_reprocessing_workflow")
        if not request.dry_run:
            run = await self.workflow_client.wait_for_completion(run.run_id)
            state.invoked_tools.append("wait_for_completion")
        state.transition(WorkflowState.VERIFYING_RECOVERY)
        recovered_context = context
        if not request.dry_run:
            recovered_context = await self.repository.get_document_context(
                request.document_id, run.run_id
            )
            state.invoked_tools.append("get_document_context")
        after = before if request.dry_run else self.quality.evaluate(recovered_context)
        attempt = None
        if not request.dry_run:
            delta = after.final_quality_score - before.final_quality_score
            outcome = (
                "IMPROVED" if delta > 0.001 else "REGRESSED" if delta < -0.001 else "UNCHANGED"
            )
            attempt = RecoveryAttempt(
                recovery_id=f"recovery-{cid}",
                document_id=request.document_id,
                source_run_id=request.source_run_id,
                recovery_run_id=run.run_id,
                strategy=plan.strategy,
                parser_id=parser_id,
                parser_config=request.parser_config,
                approval_reference=request.approval.approval_reference or "",
                actor=request.actor,
                status=run.status,
                before_quality_score=before.final_quality_score,
                after_quality_score=after.final_quality_score,
                outcome=outcome,
            )
            await self.repository.write_idempotent(
                "create_recovery_attempt",
                key,
                attempt.model_dump(mode="json"),
            )
            state.invoked_tools.append("create_recovery_attempt")
            await self.repository.write_idempotent(
                "record_quality_assessment",
                f"{key}:quality",
                after.model_dump(mode="json"),
            )
            state.invoked_tools.append("record_quality_assessment")
            await self.repository.write_idempotent(
                "update_processing_status",
                f"{key}:status",
                {
                    "document_id": request.document_id,
                    "run_id": run.run_id,
                    "status": "RECOVERY_VERIFIED",
                    "quality_decision": after.decision.value,
                    "actor": request.actor,
                    "approval_reference": request.approval.approval_reference,
                    "reason": request.reason,
                    "correlation_id": cid,
                },
            )
            state.invoked_tools.append("update_processing_status")
        state.transition(WorkflowState.COMPLETED)
        self._sync_audit(state, audit)
        response = AgentOperationResponse(
            correlation_id=cid,
            operation_mode=OperationMode.RECOVER,
            document_context=recovered_context,
            diagnosis=diagnosis,
            quality_assessment=after,
            recovery_plan=plan,
            recovery_attempt=attempt,
            recommended_action=plan.strategy.value,
            approval_required=not request.approval.valid(),
            execution_status=run.status,
            resulting_run_id=run.run_id,
            final_decision=after.decision.value,
            warnings=["Dry run: no write or workflow execution occurred."]
            if request.dry_run
            else [],
            audit=audit,
        )
        self.operations[cid] = response
        return response

    @traced_operation("processing_quality.compare_parsers")
    async def compare(self, request: CompareParsersRequest) -> AgentOperationResponse:
        cid, state, audit = self._ids(request.correlation_id, request.actor)
        metrics = await self.repository.parser_metrics(request.parser_candidates)
        state.invoked_tools.append("get_parser_metrics")
        state.transition(WorkflowState.CONTEXT_LOADED)
        state.transition(WorkflowState.VALIDATING)
        comparison = self.comparison.compare(metrics, request.quality_weight_profile)
        state.transition(WorkflowState.COMPLETED)
        self._sync_audit(state, audit)
        response = AgentOperationResponse(
            correlation_id=cid,
            operation_mode=OperationMode.COMPARE_PARSERS,
            parser_comparison=comparison,
            recommended_action=f"Recommend {comparison.recommended_parser_id}; production policy unchanged.",
            final_decision="RECOMMENDATION_ONLY",
            audit=audit,
        )
        self.operations[cid] = response
        return response

    @traced_operation("processing_quality.optimize_policy")
    async def optimize(self, request: OptimizePolicyRequest) -> AgentOperationResponse:
        cid, state, audit = self._ids(request.correlation_id, request.actor)
        metrics = await self.repository.parser_metrics(request.allowed_parser_candidates)
        state.invoked_tools.append("get_parser_metrics")
        state.transition(WorkflowState.CONTEXT_LOADED)
        state.transition(WorkflowState.VALIDATING)
        comparison = self.comparison.compare(metrics, request.optimization_profile)
        policy_yaml = self.optimization.propose(request.document_class, comparison)
        if request.apply and not request.dry_run:
            require_approval(request.approval)
            key = idempotency_key(
                "routing-policy",
                request.document_class,
                "policy-proposal",
                comparison.recommended_parser_id,
                {
                    "current": request.current_routing_policy,
                    "candidates": request.allowed_parser_candidates,
                    "proposal": policy_yaml,
                },
            )
            await self.repository.write_idempotent(
                "apply_approved_routing_policy",
                key,
                {
                    "document_class": request.document_class,
                    "policy_yaml": policy_yaml,
                    "actor": request.actor,
                    "approval_reference": request.approval.approval_reference,
                    "correlation_id": cid,
                },
            )
            state.invoked_tools.append("apply_approved_routing_policy")
        state.transition(WorkflowState.COMPLETED)
        self._sync_audit(state, audit)
        response = AgentOperationResponse(
            correlation_id=cid,
            operation_mode=OperationMode.OPTIMIZE_POLICY,
            parser_comparison=comparison,
            proposed_policy_yaml=policy_yaml,
            recommended_action="Review proposed routing policy; approval required to apply.",
            approval_required=not (request.apply and request.approval.valid()),
            final_decision="PROPOSED"
            if not request.apply
            else "APPLIED"
            if not request.dry_run
            else "DRY_RUN",
            audit=audit,
        )
        self.operations[cid] = response
        return response
