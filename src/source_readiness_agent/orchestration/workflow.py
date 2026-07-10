"""Top-level orchestrator with transport-independent methods."""

from uuid import uuid4

from source_readiness_agent.models.contracts import AuditMetadata, OperationResult
from source_readiness_agent.models.requests import (
    ActivateConfigurationRequest,
    AssessSourceRequest,
    GenerateConfigurationRequest,
    SampleRunRequest,
    ValidateConfigurationRequest,
)
from source_readiness_agent.services.activation_service import ActivationService
from source_readiness_agent.services.assessment_service import AssessmentService
from source_readiness_agent.services.configuration_service import ConfigurationService
from source_readiness_agent.services.sample_run_service import SampleRunService
from source_readiness_agent.services.validation_service import ValidationService
from source_readiness_agent.tools.repository import InMemoryRepository


class SourceReadinessOrchestrator:
    def __init__(
        self,
        repository: InMemoryRepository,
        assessment: AssessmentService,
        configuration: ConfigurationService,
        validation: ValidationService,
        sample_run: SampleRunService,
        activation: ActivationService,
    ) -> None:
        self.repository = repository
        self.assessment_service = assessment
        self.configuration_service = configuration
        self.validation_service = validation
        self.sample_run_service = sample_run
        self.activation_service = activation

    @staticmethod
    def _correlation(value: str | None) -> str:
        return value or f"CORR-{uuid4().hex[:16].upper()}"

    async def assess_source(self, request: AssessSourceRequest) -> OperationResult:
        correlation = self._correlation(request.correlation_id)
        assessment = await self.assessment_service.assess(request)
        result = OperationResult(
            correlation_id=correlation,
            operation_mode="ASSESS_SOURCE",
            source_summary={
                "source_id": request.source.source_id,
                "source_name": request.source.source_name,
                "source_type": request.source.source_type.value,
            },
            source_profile=assessment.source_profile,
            readiness_assessment=assessment,
            approval_required=False,
            next_actions=assessment.recommended_actions,
            audit_metadata=AuditMetadata(
                actor=request.actor, reason=request.reason, correlation_id=correlation
            ),
        )
        self.repository.record_operation(result)
        return result

    async def generate_configuration(
        self, request: GenerateConfigurationRequest
    ) -> OperationResult:
        correlation = self._correlation(request.correlation_id)
        proposal = self.configuration_service.generate(request)
        assessment = self.repository.get_assessment(proposal.assessment_id)
        result = OperationResult(
            correlation_id=correlation,
            operation_mode="GENERATE_CONFIGURATION",
            source_summary={"source_id": proposal.source_id},
            source_profile=assessment.source_profile,
            readiness_assessment=assessment,
            configuration_proposal=proposal,
            approval_required=True,
            next_actions=[
                "Validate the deterministic configuration",
                "Obtain approval before a sample run",
            ],
            audit_metadata=AuditMetadata(
                actor=request.actor, reason=request.reason, correlation_id=correlation
            ),
        )
        self.repository.record_operation(result)
        return result

    async def validate_configuration(
        self, request: ValidateConfigurationRequest
    ) -> OperationResult:
        correlation = self._correlation(request.correlation_id)
        proposal, validation = self.validation_service.validate(request)
        result = OperationResult(
            correlation_id=correlation,
            operation_mode="VALIDATE_CONFIGURATION",
            source_summary={"source_id": proposal.source_id},
            configuration_proposal=proposal,
            validation_result=validation,
            approval_required=not bool(validation.errors),
            next_actions=validation.remediation or ["Obtain approval for a controlled sample run"],
            audit_metadata=AuditMetadata(
                actor=request.actor, reason="validate configuration", correlation_id=correlation
            ),
        )
        self.repository.record_operation(result)
        return result

    async def sample_run(self, request: SampleRunRequest) -> OperationResult:
        correlation = self._correlation(request.correlation_id)
        run = await self.sample_run_service.run(request, correlation)
        proposal = self.repository.get_proposal(run.proposal_id)
        result = OperationResult(
            correlation_id=correlation,
            operation_mode="SAMPLE_RUN",
            source_summary={"source_id": run.source_id},
            configuration_proposal=proposal,
            sample_run=run,
            approval_required=True,
            next_actions=[
                "Review sample metrics",
                "Enable and approve activation only after governance review",
            ],
            audit_metadata=AuditMetadata(
                actor=request.actor,
                reason="controlled sample run",
                correlation_id=correlation,
                approval_reference=request.approval.approval_reference,
            ),
        )
        self.repository.record_operation(result)
        return result

    async def activate(self, request: ActivateConfigurationRequest) -> OperationResult:
        correlation = self._correlation(request.correlation_id)
        proposal = self.activation_service.activate(request, correlation)
        result = OperationResult(
            correlation_id=correlation,
            operation_mode="ACTIVATE_CONFIGURATION",
            source_summary={"source_id": proposal.source_id, "active_version": proposal.version},
            configuration_proposal=proposal,
            approval_required=True,
            next_actions=["Monitor the first production ingestion batch"],
            audit_metadata=AuditMetadata(
                actor=request.actor,
                reason="approved activation",
                correlation_id=correlation,
                approval_reference=request.approval.approval_reference,
            ),
        )
        self.repository.record_operation(result)
        return result
