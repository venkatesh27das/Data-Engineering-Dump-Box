"""FastAPI Databricks App transport."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from source_readiness_agent.agent import SourceReadinessResponsesAgent, parse_responses_request
from source_readiness_agent.config import Settings, get_settings
from source_readiness_agent.connectors.mock import MockConnector
from source_readiness_agent.logging_config import configure_logging
from source_readiness_agent.models.requests import (
    ActivateConfigurationRequest,
    AssessSourceRequest,
    GenerateConfigurationRequest,
    SampleRunRequest,
    ValidateConfigurationRequest,
)
from source_readiness_agent.orchestration.workflow import SourceReadinessOrchestrator
from source_readiness_agent.services.activation_service import ActivationService
from source_readiness_agent.services.assessment_service import AssessmentService
from source_readiness_agent.services.configuration_service import ConfigurationService
from source_readiness_agent.services.sample_run_service import SampleRunService
from source_readiness_agent.services.validation_service import ValidationService
from source_readiness_agent.tools.base import ApprovalRequired
from source_readiness_agent.tools.repository import InMemoryRepository
from source_readiness_agent.tools.workflow_client import DatabricksWorkflowClient


@dataclass
class Runtime:
    repository: InMemoryRepository
    orchestrator: SourceReadinessOrchestrator
    agent: SourceReadinessResponsesAgent


def build_runtime(settings: Settings) -> Runtime:
    repository = InMemoryRepository()
    fixture_root = Path("tests/fixtures/mock_source").resolve()
    mock = MockConnector(fixture_root, settings.source_allowlist)
    connectors = {"MOCK": mock}
    supported = {
        "pdf",
        "docx",
        "pptx",
        "png",
        "jpg",
        "jpeg",
        "tif",
        "tiff",
        "txt",
        "html",
        "htm",
        "xml",
        "json",
    }
    assessment = AssessmentService(repository, settings, connectors, supported)
    configuration = ConfigurationService(repository, settings)
    validation = ValidationService(repository, settings)
    workflow = DatabricksWorkflowClient(
        settings.databricks_workflow_job_id, enabled=not settings.use_mock_tools
    )
    sample = SampleRunService(repository, workflow)
    activation = ActivationService(repository, settings)
    orchestrator = SourceReadinessOrchestrator(
        repository, assessment, configuration, validation, sample, activation
    )
    return Runtime(repository, orchestrator, SourceReadinessResponsesAgent(orchestrator))


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    runtime = build_runtime(settings)
    api = FastAPI(title="Source Readiness & Pipeline Configuration Agent", version="0.1.0")
    api.state.runtime = runtime

    @api.exception_handler(ApprovalRequired)
    async def approval_error(_request: Request, exc: ApprovalRequired) -> JSONResponse:
        return JSONResponse(
            status_code=403, content={"detail": str(exc), "error_code": "APPROVAL_REQUIRED"}
        )

    @api.exception_handler(PermissionError)
    async def permission_error(_request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=403, content={"detail": str(exc), "error_code": "FORBIDDEN"}
        )

    @api.exception_handler(KeyError)
    async def not_found(_request: Request, _exc: KeyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "requested record was not found"})

    @api.exception_handler(ValueError)
    async def bad_request(_request: Request, exc: ValueError) -> JSONResponse:
        detail = "request validation failed" if isinstance(exc, ValidationError) else str(exc)
        return JSONResponse(status_code=422, content={"detail": detail})

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @api.get("/ready")
    async def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "environment": settings.app_env,
            "mock_mode": settings.use_mock_tools,
            "activation_enabled": settings.activation_enabled,
        }

    @api.post("/invocations")
    async def invocations(body: dict[str, object]) -> dict[str, object]:
        mode, payload = parse_responses_request(body)
        output = await runtime.agent.invoke_structured(mode, payload)
        return {
            "id": output["correlation_id"],
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": __import__("json").dumps(output)}],
                }
            ],
            "source_readiness_result": output,
        }

    @api.post("/api/v1/assess-source")
    async def assess_source(body: AssessSourceRequest) -> dict[str, object]:
        return (await runtime.orchestrator.assess_source(body)).model_dump(mode="json")

    @api.post("/api/v1/generate-configuration")
    async def generate_configuration(body: GenerateConfigurationRequest) -> dict[str, object]:
        return (await runtime.orchestrator.generate_configuration(body)).model_dump(mode="json")

    @api.post("/api/v1/validate-configuration")
    async def validate_configuration(body: ValidateConfigurationRequest) -> dict[str, object]:
        return (await runtime.orchestrator.validate_configuration(body)).model_dump(mode="json")

    @api.post("/api/v1/sample-run")
    async def sample_run(body: SampleRunRequest) -> dict[str, object]:
        return (await runtime.orchestrator.sample_run(body)).model_dump(mode="json")

    @api.post("/api/v1/activate")
    async def activate(body: ActivateConfigurationRequest) -> dict[str, object]:
        return (await runtime.orchestrator.activate(body)).model_dump(mode="json")

    @api.get("/api/v1/operations/{correlation_id}")
    async def get_operation(correlation_id: str) -> dict[str, object]:
        return runtime.repository.operations[correlation_id].model_dump(mode="json")

    @api.get("/api/v1/assessments/{assessment_id}")
    async def get_assessment(assessment_id: str) -> dict[str, object]:
        return runtime.repository.get_assessment(assessment_id).model_dump(mode="json")

    @api.get("/api/v1/proposals/{proposal_id}")
    async def get_proposal(proposal_id: str) -> dict[str, object]:
        return runtime.repository.get_proposal(proposal_id).model_dump(mode="json")

    return api


app = create_app()
