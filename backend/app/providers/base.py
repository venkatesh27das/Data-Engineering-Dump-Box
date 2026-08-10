from abc import ABC, abstractmethod
from typing import Literal, TypeVar

from pydantic import BaseModel, Field

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class ModelProviderError(RuntimeError):
    pass


class ModelProviderConnectionError(ModelProviderError):
    pass


class StructuredOutputError(ModelProviderError):
    pass


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatResponse(BaseModel):
    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class ModelProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    @abstractmethod
    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError
