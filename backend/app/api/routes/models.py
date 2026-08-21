from typing import Any

from fastapi import APIRouter, Depends

from app.agents.runtime import AgentRuntime
from app.api.dependencies import get_agent_runtime, get_models
from app.llm.model_registry import ModelRegistry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
def model_status(models: ModelRegistry = Depends(get_models)) -> dict[str, Any]:
    return models.status()


@router.get("")
def list_models(models: ModelRegistry = Depends(get_models)) -> list[str]:
    return models.status()["available_models"]


@router.put("/config")
def update_model_config(
    payload: dict[str, str], models: ModelRegistry = Depends(get_models)
) -> dict[str, Any]:
    return models.update(payload)


@router.post("/probe")
def probe_model_capabilities(
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict[str, Any]:
    return runtime.probe()
