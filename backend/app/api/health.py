from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.graph.base import GraphStore
from app.graph.dependencies import get_graph_store
from app.providers.base import ModelProvider
from app.providers.dependencies import get_model_provider

router = APIRouter(tags=["health"])

IntegrationStatus = Literal["connected", "disconnected", "not_configured", "configuration_pending"]


class HealthResponse(BaseModel):
    api: Literal["ok"] = "ok"
    lmstudio: IntegrationStatus
    neo4j: IntegrationStatus


async def _neo4j_status(graph_store: GraphStore) -> IntegrationStatus:
    if not graph_store.configured:
        return "not_configured"
    return "connected" if await graph_store.health_check() else "disconnected"


@router.get("/health", response_model=HealthResponse)
async def health(
    model_provider: ModelProvider = Depends(get_model_provider),
    graph_store: GraphStore = Depends(get_graph_store),
) -> HealthResponse:
    """Report API readiness and external integration health."""
    return HealthResponse(
        lmstudio="connected" if await model_provider.health_check() else "disconnected",
        neo4j=await _neo4j_status(graph_store),
    )
