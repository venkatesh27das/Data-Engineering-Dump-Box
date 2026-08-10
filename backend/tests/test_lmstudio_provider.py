import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.providers.base import ChatMessage, ModelProviderConnectionError, StructuredOutputError
from app.providers.lmstudio import LMStudioProvider
from app.providers.model_config import load_model_configuration


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _StructuredAnswer(BaseModel):
    name: str
    confidence: float


def test_model_configuration_expands_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LMSTUDIO_KNOWLEDGE_MODEL", "local-knowledge")
    config = load_model_configuration(Path(__file__).parents[1] / "config" / "models.yaml")
    assert config.lmstudio.base_url == "http://localhost:1234/v1"
    assert config.models.knowledge.name == "local-knowledge"


@pytest.mark.anyio
async def test_health_chat_and_embedding() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})
        return httpx.Response(200, json={"model": "local", "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 2, "completion_tokens": 1}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", orchestrator_model="local", embedding_model="embed", client=client)
        assert await provider.health_check() is True
        response = await provider.chat([ChatMessage(role="user", content="Hi")])
        assert response.content == "hello"
        assert await provider.embed(["ACME"]) == [[0.1, 0.2]]


@pytest.mark.anyio
async def test_structured_output_retries_once_then_validates() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        content = '{"name":"ACME"}' if attempts == 1 else '{"name":"ACME","confidence":0.96}'
        request_payload = json.loads(request.content)
        assert request_payload["response_format"]["type"] == "json_schema"
        if attempts == 2:
            assert "did not validate" in request_payload["messages"][-1]["content"]
        return httpx.Response(200, json={"model": "local", "choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", knowledge_model="local", client=client)
        result = await provider.structured_generate([ChatMessage(role="user", content="Extract")], _StructuredAnswer)
    assert result.confidence == 0.96
    assert attempts == 2


@pytest.mark.anyio
async def test_structured_output_fails_after_bounded_retry() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", knowledge_model="local", client=client)
        with pytest.raises(StructuredOutputError):
            await provider.structured_generate([ChatMessage(role="user", content="Extract")], _StructuredAnswer)


@pytest.mark.anyio
async def test_timeout_is_reported_separately_from_unreachable_server() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow model", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", knowledge_model="local", timeout_seconds=45, client=client)
        with pytest.raises(ModelProviderConnectionError, match="timed out after 45 seconds"):
            await provider.structured_generate([ChatMessage(role="user", content="Extract")], _StructuredAnswer)
