from fastapi.testclient import TestClient

from app.main import app
from app.graph.dependencies import get_graph_store
from app.providers.base import ChatMessage, ChatResponse, ModelProvider, StructuredModel
from app.providers.dependencies import get_model_provider


class HealthyProvider(ModelProvider):
    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        raise NotImplementedError

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


client = TestClient(app)


class HealthyGraphStore:
    configured = True

    async def health_check(self) -> bool:
        return True


class UnconfiguredGraphStore:
    configured = False

    async def health_check(self) -> bool:
        return False


def test_versioned_health_endpoint_reports_api_ready() -> None:
    app.dependency_overrides[get_model_provider] = HealthyProvider
    app.dependency_overrides[get_graph_store] = UnconfiguredGraphStore
    response = client.get("/api/v1/health")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "api": "ok",
        "model_provider": "connected",
        "model_provider_name": "LM Studio",
        "lmstudio": "connected",
        "neo4j": "not_configured",
    }


def test_health_alias_is_available() -> None:
    app.dependency_overrides[get_model_provider] = HealthyProvider
    app.dependency_overrides[get_graph_store] = UnconfiguredGraphStore
    response = client.get("/health")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["api"] == "ok"


def test_health_reports_live_neo4j_connectivity() -> None:
    app.dependency_overrides[get_model_provider] = HealthyProvider
    app.dependency_overrides[get_graph_store] = HealthyGraphStore
    response = client.get("/api/v1/health")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["neo4j"] == "connected"
