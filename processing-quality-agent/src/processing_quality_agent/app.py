from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, HTTPException

from processing_quality_agent.agent import ProcessingQualityResponsesAgent
from processing_quality_agent.config import Settings, get_settings
from processing_quality_agent.logging_config import configure_logging
from processing_quality_agent.models.requests import (
    CompareParsersRequest,
    InvestigateRequest,
    OptimizePolicyRequest,
    RecoverRequest,
    ResponsesAgentRequest,
)
from processing_quality_agent.models.responses import AgentOperationResponse, ResponsesAgentOutput
from processing_quality_agent.orchestration.workflow import AgentOrchestrator
from processing_quality_agent.tools.mock_repository import InMemoryRepository
from processing_quality_agent.tools.workflow_client import (
    DatabricksWorkflowClient,
    MockWorkflowClient,
)


def build_orchestrator(settings: Settings) -> AgentOrchestrator:
    workflow: DatabricksWorkflowClient
    if not settings.use_mock_tools:
        # A workspace must bind a governed UC/MCP repository before production startup.
        # Failing closed prevents an accidentally deployed app from returning synthetic data.
        raise RuntimeError(
            "production repository is not bound; configure the project-specific governed "
            "Unity Catalog or MCP repository"
        )
    else:
        workflow, repository = MockWorkflowClient(), InMemoryRepository()
    return AgentOrchestrator(settings, repository, workflow)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = resolved
        application.state.orchestrator = build_orchestrator(resolved)
        application.state.responses_agent = ProcessingQualityResponsesAgent(
            application.state.orchestrator
        )
        try:
            import mlflow

            mlflow.set_experiment(resolved.mlflow_experiment)
        except Exception:
            pass
        yield

    api = FastAPI(
        title="Processing Quality, Recovery & Parser Optimization Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @api.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    @api.post("/invocations", response_model=ResponsesAgentOutput)
    async def invocations(request: ResponsesAgentRequest) -> ResponsesAgentOutput:
        agent = cast(ProcessingQualityResponsesAgent, api.state.responses_agent)
        return await agent.invoke(request)

    @api.post("/api/v1/investigate", response_model=AgentOperationResponse)
    async def investigate(request: InvestigateRequest) -> AgentOperationResponse:
        orchestrator = cast(AgentOrchestrator, api.state.orchestrator)
        return await orchestrator.investigate(request)

    @api.post("/api/v1/recover", response_model=AgentOperationResponse)
    async def recover(request: RecoverRequest) -> AgentOperationResponse:
        orchestrator = cast(AgentOrchestrator, api.state.orchestrator)
        return await orchestrator.recover(request)

    @api.post("/api/v1/compare-parsers", response_model=AgentOperationResponse)
    async def compare(request: CompareParsersRequest) -> AgentOperationResponse:
        orchestrator = cast(AgentOrchestrator, api.state.orchestrator)
        return await orchestrator.compare(request)

    @api.post("/api/v1/optimize-policy", response_model=AgentOperationResponse)
    async def optimize(request: OptimizePolicyRequest) -> AgentOperationResponse:
        orchestrator = cast(AgentOrchestrator, api.state.orchestrator)
        return await orchestrator.optimize(request)

    @api.get("/api/v1/operations/{correlation_id}", response_model=AgentOperationResponse)
    async def operation(correlation_id: str) -> AgentOperationResponse:
        orchestrator = cast(AgentOrchestrator, api.state.orchestrator)
        try:
            return orchestrator.operations[correlation_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="operation not found") from exc

    return api


app = create_app()
