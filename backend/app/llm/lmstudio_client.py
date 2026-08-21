import base64
import json
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import Settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LMStudioError(RuntimeError):
    """Raised when a local model capability cannot complete a request."""


class LMStudioClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.lm_studio_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.lm_studio_api_key}"}

    def structured_chat(
        self,
        model: str,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
        *,
        image: tuple[bytes, str] | None = None,
        max_tokens: int = 1400,
    ) -> SchemaT:
        if not model:
            raise LMStudioError("No model is configured for this capability")
        user_content: str | list[dict[str, Any]] = user_prompt
        if image:
            binary, media_type = image
            encoded = base64.b64encode(binary).decode("ascii")
            user_content = [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                },
            ]
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": re.sub(r"[^a-zA-Z0-9_-]", "_", schema.__name__).lower(),
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": response_format,
            "reasoning_effort": "none",
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        last_error: Exception | None = None
        for _attempt in range(self.settings.llm_max_retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=self.settings.llm_request_timeout_seconds,
                )
                response.raise_for_status()
                message = response.json()["choices"][0]["message"]
                raw = message.get("content") or message.get("reasoning_content") or ""
                return schema.model_validate(self._json_value(raw))
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
                last_error = error
        raise LMStudioError(f"Local model request failed: {last_error}") from last_error

    def embeddings(self, model: str, texts: list[str]) -> list[list[float]]:
        if not model:
            raise LMStudioError("No embedding model is configured")
        if not texts:
            return []
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers=self.headers,
                json={"model": model, "input": texts},
                timeout=self.settings.llm_request_timeout_seconds,
            )
            response.raise_for_status()
            ordered = sorted(response.json().get("data", []), key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
            if len(vectors) != len(texts):
                raise LMStudioError("Embedding response did not contain one vector per input")
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LMStudioError(f"Local embedding request failed: {error}") from error

    @staticmethod
    def _json_value(raw: Any) -> Any:
        if isinstance(raw, (dict, list)):
            return raw
        text = str(raw).strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = min((index for index in (text.find("{"), text.find("[")) if index >= 0), default=-1)
            end = max(text.rfind("}"), text.rfind("]"))
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise
