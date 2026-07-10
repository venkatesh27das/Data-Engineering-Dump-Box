from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from processing_quality_agent.models.requests import (
    CompareParsersRequest,
    InvestigateRequest,
    OptimizePolicyRequest,
    RecoverRequest,
    ResponsesAgentRequest,
)
from processing_quality_agent.models.responses import AgentOperationResponse, ResponsesAgentOutput
from processing_quality_agent.orchestration.workflow import AgentOrchestrator

try:
    from mlflow.pyfunc import ResponsesAgent as _ResponsesAgentBase
except (ImportError, AttributeError):

    class _ResponsesAgentBase:  # type: ignore[no-redef]
        """Local compatibility base when the MLflow ResponsesAgent is unavailable."""


class ProcessingQualityResponsesAgent(_ResponsesAgentBase):  # type: ignore[misc]
    """Databricks ResponsesAgent-compatible wrapper isolated from domain logic."""

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orchestrator = orchestrator

    async def invoke(self, request: ResponsesAgentRequest) -> ResponsesAgentOutput:
        custom = dict(request.custom_inputs)
        mode = str(custom.pop("mode", "INVESTIGATE")).upper()
        result: AgentOperationResponse
        if mode == "RECOVER":
            result = await self.orchestrator.recover(RecoverRequest.model_validate(custom))
        elif mode == "COMPARE_PARSERS":
            result = await self.orchestrator.compare(CompareParsersRequest.model_validate(custom))
        elif mode == "OPTIMIZE_POLICY":
            result = await self.orchestrator.optimize(OptimizePolicyRequest.model_validate(custom))
        else:
            question = self._text(request.input)
            custom.setdefault("question", question)
            result = await self.orchestrator.investigate(InvestigateRequest.model_validate(custom))
        text = (
            result.diagnosis.explanation
            if result.diagnosis
            else result.recommended_action or "Operation completed."
        )
        return ResponsesAgentOutput(
            id=f"resp_{uuid4().hex}",
            created_at=int(time.time()),
            output=[
                {
                    "type": "message",
                    "id": f"msg_{uuid4().hex}",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ],
            custom_outputs=result.model_dump(mode="json"),
        )

    def predict(
        self,
        context: Any,
        model_input: dict[str, Any] | ResponsesAgentRequest,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synchronous MLflow pyfunc entrypoint used during model serving."""
        import asyncio

        request = (
            model_input
            if isinstance(model_input, ResponsesAgentRequest)
            else ResponsesAgentRequest.model_validate(model_input)
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.invoke(request)).model_dump(mode="json")
        raise RuntimeError("predict cannot run inside an event loop; use invoke")

    @staticmethod
    def _text(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        texts = []
        for item in value:
            content = item.content
            if isinstance(content, str):
                texts.append(content)
            else:
                for part in content:
                    if "text" in part:
                        texts.append(str(part["text"]))
        return "\n".join(texts) or None
