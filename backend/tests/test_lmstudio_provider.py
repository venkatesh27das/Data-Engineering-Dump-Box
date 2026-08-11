import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.providers.base import ChatMessage, ModelProviderConnectionError, StructuredOutputError
from app.config import Settings
from app.providers.dependencies import get_model_provider
from app.providers.lmstudio import LMStudioProvider, OpenAICompatibleProvider
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
async def test_openai_compatible_provider_sends_gateway_bearer_credentials() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer gateway-secret"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gateway-model"}]})
        return httpx.Response(
            200,
            json={"model": "gateway-model", "choices": [{"message": {"content": "gateway response"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            base_url="https://gateway.test/v1",
            api_key="gateway-secret",
            orchestrator_model="gateway-model",
            client=client,
        )
        assert await provider.health_check() is True
        response = await provider.chat([ChatMessage(role="user", content="Hello")])
    assert response.content == "gateway response"


def test_provider_dependency_selects_openai_compatible_gateway() -> None:
    settings = Settings(
        ai_provider="openai_compatible",
        openai_compatible_base_url="https://gateway.test/v1",
        openai_compatible_api_key="gateway-secret",
        openai_compatible_orchestrator_model="planner-model",
        openai_compatible_knowledge_model="extraction-model",
    )

    provider = get_model_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert not isinstance(provider, LMStudioProvider)
    assert provider.base_url == "https://gateway.test/v1"
    assert provider.api_key == "gateway-secret"
    assert provider.orchestrator_model == "planner-model"
    assert provider.knowledge_model == "extraction-model"


@pytest.mark.anyio
async def test_structured_output_retries_once_then_validates() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        content = '{"name":"ACME"}' if attempts == 1 else '{"name":"ACME","confidence":0.96}'
        request_payload = json.loads(request.content)
        assert request_payload["response_format"]["type"] == "json_schema"
        assert request_payload["max_tokens"] == 2048
        if attempts == 2:
            assert "did not validate" in request_payload["messages"][-1]["content"]
        return httpx.Response(200, json={"model": "local", "choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", knowledge_model="local", client=client)
        result = await provider.structured_generate(
            [ChatMessage(role="user", content="Extract")],
            _StructuredAnswer,
            max_tokens=2048,
        )
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
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow model", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(
            base_url="http://lmstudio.test/v1",
            knowledge_model="local",
            timeout_seconds=45,
            connect_timeout_seconds=7,
            client=client,
        )
        assert provider.timeout.read == 45
        assert provider.timeout.connect == 7
        with pytest.raises(ModelProviderConnectionError, match="timed out after 45 seconds"):
            await provider.structured_generate([ChatMessage(role="user", content="Extract")], _StructuredAnswer)
    assert attempts == 2


@pytest.mark.anyio
async def test_read_timeout_retry_can_recover() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("slow first attempt", request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"name":"ACME","confidence":0.96}'}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LMStudioProvider(base_url="http://lmstudio.test/v1", knowledge_model="local", client=client)
        result = await provider.structured_generate(
            [ChatMessage(role="user", content="Extract")],
            _StructuredAnswer,
        )
    assert result.name == "ACME"
    assert attempts == 2
