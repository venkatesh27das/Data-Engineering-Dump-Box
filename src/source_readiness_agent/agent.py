"""Databricks ResponsesAgent-compatible wrapper isolated from business logic."""

from __future__ import annotations

import json
from typing import Any

from source_readiness_agent.models.requests import (
    ActivateConfigurationRequest,
    AssessSourceRequest,
    GenerateConfigurationRequest,
    SampleRunRequest,
    ValidateConfigurationRequest,
)
from source_readiness_agent.orchestration.workflow import SourceReadinessOrchestrator

try:  # Databricks Apps runtime
    from databricks.sdk.service.serving import ChatMessage  # noqa: F401
    from mlflow.pyfunc import ResponsesAgent as MLflowResponsesAgent
except ImportError:  # local mode

    class MLflowResponsesAgent:  # type: ignore[no-redef]
        pass


class SourceReadinessResponsesAgent(MLflowResponsesAgent):  # type: ignore[misc]
    """Strict structured dispatcher; it is not a generic chatbot."""

    def __init__(self, orchestrator: SourceReadinessOrchestrator) -> None:
        self.orchestrator = orchestrator

    async def invoke_structured(self, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        if mode == "ASSESS_SOURCE":
            result = await self.orchestrator.assess_source(
                AssessSourceRequest.model_validate(payload)
            )
        elif mode == "GENERATE_CONFIGURATION":
            result = await self.orchestrator.generate_configuration(
                GenerateConfigurationRequest.model_validate(payload)
            )
        elif mode == "VALIDATE_CONFIGURATION":
            result = await self.orchestrator.validate_configuration(
                ValidateConfigurationRequest.model_validate(payload)
            )
        elif mode == "SAMPLE_RUN":
            result = await self.orchestrator.sample_run(SampleRunRequest.model_validate(payload))
        elif mode == "ACTIVATE_CONFIGURATION":
            result = await self.orchestrator.activate(
                ActivateConfigurationRequest.model_validate(payload)
            )
        else:
            raise ValueError("ResponsesAgent requests must specify a supported operation_mode")
        return result.model_dump(mode="json")

    def predict(self, request: dict[str, Any]) -> dict[str, Any]:
        """Synchronous MLflow contract. FastAPI uses invoke_structured directly."""
        import asyncio

        mode, payload = parse_responses_request(request)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.invoke_structured(mode, payload))
        raise RuntimeError("predict cannot be called inside an event loop; use invoke_structured")


def parse_responses_request(request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "operation_mode" in request and "payload" in request:
        return str(request["operation_mode"]), dict(request["payload"])
    inputs = request.get("input")
    if not isinstance(inputs, list):
        raise ValueError("input must be a Responses-compatible list")
    for item in reversed(inputs):
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        text = (
            content
            if isinstance(content, str)
            else next(
                (
                    part.get("text")
                    for part in content or []
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ),
                None,
            )
        )
        if text:
            value = json.loads(text)
            if isinstance(value, dict) and "operation_mode" in value and "payload" in value:
                return str(value["operation_mode"]), dict(value["payload"])
    raise ValueError("Responses input must contain JSON with operation_mode and payload")
