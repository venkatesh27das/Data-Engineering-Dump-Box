import json
import threading
from typing import Any

import httpx

from app.core.config import Settings


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_path = settings.storage_root.parent / "model_config.json"
        self.lock = threading.Lock()
        self._load_saved_config()

    def update(self, payload: dict[str, str]) -> dict[str, Any]:
        mapping = {
            "reasoning_model": "llm_reasoning_model",
            "vision_model": "llm_vision_model",
            "embedding_model": "embedding_model",
        }
        with self.lock:
            for key, attribute in mapping.items():
                if key in payload:
                    setattr(self.settings, attribute, str(payload[key]).strip())
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(
                    {key: getattr(self.settings, attribute) for key, attribute in mapping.items()},
                    indent=2,
                ),
                encoding="utf-8",
            )
        return self.status()

    def status(self) -> dict[str, Any]:
        models: list[str] = []
        reachable = False
        try:
            response = httpx.get(
                f"{self.settings.lm_studio_base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.settings.lm_studio_api_key}"},
                timeout=2.0,
            )
            response.raise_for_status()
            models = [item["id"] for item in response.json().get("data", []) if item.get("id")]
            reachable = True
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            pass
        reasoning, reasoning_source = self._resolve_reasoning(models)
        vision, vision_source = self._resolve_vision(models, reasoning)
        embedding, embedding_source = self._resolve_embedding(models)
        required = [reasoning]
        if self.settings.enable_vision:
            required.append(vision)
        if self.settings.enable_embeddings:
            required.append(embedding)
        valid = reachable and all(required)
        roles = {
            "reasoning": self._role(reasoning, reasoning_source, models, True),
            "vision": self._role(vision, vision_source, models, self.settings.enable_vision),
            "embedding": self._role(embedding, embedding_source, models, self.settings.enable_embeddings),
        }
        return {
            "reachable": reachable,
            "available_models": models,
            "reasoning_model": reasoning,
            "vision_model": vision,
            "embedding_model": embedding,
            "roles": roles,
            "capability_check": "ready"
            if valid
            else "required_role_missing"
            if reachable
            else "offline_deterministic_fallback",
        }

    def _load_saved_config(self) -> None:
        if not self.config_path.is_file():
            return
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        mapping = {
            "reasoning_model": "llm_reasoning_model",
            "vision_model": "llm_vision_model",
            "embedding_model": "embedding_model",
        }
        for key, attribute in mapping.items():
            if isinstance(payload.get(key), str):
                setattr(self.settings, attribute, payload[key].strip())

    def _resolve_reasoning(self, models: list[str]) -> tuple[str, str]:
        configured = self.settings.llm_reasoning_model
        if configured:
            return (configured, "configured") if configured in models else ("", "configured_missing")
        if not self.settings.auto_select_models:
            return "", "not_configured"
        candidates = [model for model in models if not self._is_embedding(model)]
        preferred = next(
            (model for model in candidates if "qwen3.5-9b" in model.casefold()),
            next((model for model in candidates if "qwen" in model.casefold()), ""),
        )
        return (preferred or (candidates[0] if candidates else "")), "auto"

    def _resolve_vision(self, models: list[str], reasoning: str) -> tuple[str, str]:
        configured = self.settings.llm_vision_model
        if configured:
            return (configured, "configured") if configured in models else ("", "configured_missing")
        if not self.settings.auto_select_models:
            return "", "not_configured"
        candidates = [model for model in models if not self._is_embedding(model)]
        preferred = next(
            (
                model
                for model in candidates
                if any(token in model.casefold() for token in ("vision", "vl", "gemma-4"))
            ),
            reasoning,
        )
        return preferred, "auto"

    def _resolve_embedding(self, models: list[str]) -> tuple[str, str]:
        configured = self.settings.embedding_model
        if configured:
            return (configured, "configured") if configured in models else ("", "configured_missing")
        if not self.settings.auto_select_models:
            return "", "not_configured"
        selected = next((model for model in models if self._is_embedding(model)), "")
        return selected, "auto"

    @staticmethod
    def _is_embedding(model: str) -> bool:
        lowered = model.casefold()
        return any(token in lowered for token in ("embed", "bge-", "e5-", "gte-"))

    @staticmethod
    def _role(model: str, source: str, models: list[str], enabled: bool) -> dict[str, Any]:
        return {
            "model": model,
            "selection": source,
            "enabled": enabled,
            "available": bool(model and model in models),
            "status": "disabled" if not enabled else "ready" if model and model in models else "missing",
        }
