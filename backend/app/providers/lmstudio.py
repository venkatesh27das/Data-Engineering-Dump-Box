import json
from collections.abc import Mapping

import httpx
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.providers.base import (
    ChatMessage,
    ChatResponse,
    ModelProvider,
    ModelProviderConnectionError,
    ModelProviderError,
    StructuredModel,
    StructuredOutputError,
)


class LMStudioProvider(ModelProvider):
    def __init__(self, *, base_url: str, orchestrator_model: str = "", knowledge_model: str = "", embedding_model: str = "", timeout_seconds: float = 30, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.orchestrator_model = orchestrator_model
        self.knowledge_model = knowledge_model
        self.embedding_model = embedding_model
        self.timeout_seconds = timeout_seconds
        self.timeout = httpx.Timeout(timeout_seconds)
        self.client = client

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            if self.client is not None:
                response = await self.client.request(method, f"{self.base_url}{path}", **kwargs)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            raise ModelProviderError(f"LM Studio returned HTTP {error.response.status_code}") from error
        except httpx.TimeoutException as error:
            raise ModelProviderConnectionError(f"LM Studio request timed out after {self.timeout_seconds:g} seconds") from error
        except httpx.HTTPError as error:
            raise ModelProviderConnectionError("LM Studio is not reachable") from error

    @staticmethod
    def _messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
        return [message.model_dump() for message in messages]

    async def _completion(self, payload: Mapping[str, object]) -> dict[str, object]:
        response = await self._request("POST", "/chat/completions", json=dict(payload))
        try:
            result = response.json()
        except ValueError as error:
            raise ModelProviderError("LM Studio returned a non-JSON completion response") from error
        if not isinstance(result, dict):
            raise ModelProviderError("LM Studio returned an invalid completion response")
        return result

    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        selected_model = model or self.orchestrator_model or self.knowledge_model
        if not selected_model:
            raise ModelProviderError("No LM Studio chat model is configured")
        payload: dict[str, object] = {"model": selected_model, "messages": self._messages(messages), "temperature": temperature}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        result = await self._completion(payload)
        try:
            choices = result["choices"]
            choice = choices[0]  # type: ignore[index]
            usage = result.get("usage", {})
            return ChatResponse(content=choice["message"]["content"], model=str(result.get("model", selected_model)), finish_reason=choice.get("finish_reason"), prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"))
        except (KeyError, IndexError, TypeError, ValidationError) as error:
            raise ModelProviderError("LM Studio completion response is missing required fields") from error

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        selected_model = model or self.knowledge_model or self.orchestrator_model
        if not selected_model:
            raise ModelProviderError("No LM Studio knowledge model is configured")
        current_messages = list(messages)
        validation_error = "unknown validation error"
        for attempt in range(2):
            payload: dict[str, object] = {
                "model": selected_model,
                "messages": self._messages(current_messages),
                "temperature": temperature,
                "response_format": {"type": "json_schema", "json_schema": {"name": response_model.__name__, "strict": True, "schema": response_model.model_json_schema()}},
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            result = await self._completion(payload)
            try:
                choices = result["choices"]
                choice = choices[0]  # type: ignore[index]
                content = choice["message"]["content"]
                return response_model.model_validate_json(content)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
                validation_error = str(error)
                if attempt == 0:
                    current_messages.append(ChatMessage(role="user", content="Your previous response did not validate against the required JSON schema. Correct it and return JSON only. " f"Validation error: {validation_error[:1000]}"))
        raise StructuredOutputError(f"LM Studio structured output failed validation after one retry: {validation_error}")

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        selected_model = model or self.embedding_model
        if not selected_model:
            raise ModelProviderError("No LM Studio embedding model is configured")
        response = await self._request("POST", "/embeddings", json={"model": selected_model, "input": texts})
        try:
            payload = response.json()
            rows = sorted(payload["data"], key=lambda item: item["index"])
            embeddings = [[float(value) for value in row["embedding"]] for row in rows]
        except (KeyError, TypeError, ValueError) as error:
            raise ModelProviderError("LM Studio returned an invalid embedding response") from error
        if len(embeddings) != len(texts):
            raise ModelProviderError("LM Studio returned an unexpected number of embeddings")
        return embeddings

    async def health_check(self) -> bool:
        if not self.base_url:
            return False
        try:
            await self._request("GET", "/models")
        except ModelProviderError:
            return False
        return True

    def as_langchain_chat_model(self, role: str = "orchestrator") -> ChatOpenAI:
        selected_model = self.orchestrator_model if role == "orchestrator" else self.knowledge_model
        selected_model = selected_model or self.knowledge_model or self.orchestrator_model
        if not selected_model:
            raise ModelProviderError(f"No LM Studio {role} model is configured")
        return ChatOpenAI(
            model=selected_model,
            base_url=self.base_url,
            api_key="lm-studio",
            temperature=0.1 if role == "knowledge" else 0.2,
            timeout=self.timeout_seconds,
            max_retries=1,
        )
