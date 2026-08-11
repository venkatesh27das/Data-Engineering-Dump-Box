from fastapi import Depends

from app.config import Settings, get_settings
from app.providers.base import ModelProvider
from app.providers.lmstudio import LMStudioProvider, OpenAICompatibleProvider
from app.providers.model_config import load_model_configuration


def get_model_provider(settings: Settings = Depends(get_settings)) -> ModelProvider:
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            orchestrator_model=settings.openai_compatible_orchestrator_model,
            knowledge_model=settings.openai_compatible_knowledge_model,
            embedding_model=settings.openai_compatible_embedding_model,
            provider_label="OpenAI-compatible gateway",
            timeout_seconds=settings.openai_compatible_timeout_seconds,
            connect_timeout_seconds=settings.openai_compatible_connect_timeout_seconds,
        )
    config = load_model_configuration(settings.repository_root / "backend" / "config" / "models.yaml")
    return LMStudioProvider(
        base_url=config.lmstudio.base_url or settings.lmstudio_base_url,
        orchestrator_model=config.models.orchestrator.name or settings.lmstudio_orchestrator_model,
        knowledge_model=config.models.knowledge.name or settings.lmstudio_knowledge_model,
        embedding_model=config.models.embedding.name or settings.lmstudio_embedding_model,
        timeout_seconds=settings.lmstudio_timeout_seconds,
        connect_timeout_seconds=settings.lmstudio_connect_timeout_seconds,
    )
