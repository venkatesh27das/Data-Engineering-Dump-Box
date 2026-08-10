from fastapi import Depends

from app.config import Settings, get_settings
from app.providers.base import ModelProvider
from app.providers.lmstudio import LMStudioProvider
from app.providers.model_config import load_model_configuration


def get_model_provider(settings: Settings = Depends(get_settings)) -> ModelProvider:
    config = load_model_configuration(settings.repository_root / "backend" / "config" / "models.yaml")
    return LMStudioProvider(
        base_url=config.lmstudio.base_url or settings.lmstudio_base_url,
        orchestrator_model=config.models.orchestrator.name or settings.lmstudio_orchestrator_model,
        knowledge_model=config.models.knowledge.name or settings.lmstudio_knowledge_model,
        embedding_model=config.models.embedding.name or settings.lmstudio_embedding_model,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )
