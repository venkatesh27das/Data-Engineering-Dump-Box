import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelRoleConfig(BaseModel):
    name: str = ""
    temperature: float = Field(default=0.1, ge=0, le=2)


class EmbeddingModelConfig(BaseModel):
    name: str = ""


class LMStudioConfig(BaseModel):
    base_url: str


class ModelsConfig(BaseModel):
    orchestrator: ModelRoleConfig
    knowledge: ModelRoleConfig
    embedding: EmbeddingModelConfig


class ModelConfiguration(BaseModel):
    lmstudio: LMStudioConfig
    models: ModelsConfig


_ENV_REFERENCE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_environment(value: object) -> object:
    if isinstance(value, str):
        return _ENV_REFERENCE.sub(lambda match: os.getenv(match.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    return value


def load_model_configuration(path: Path) -> ModelConfiguration:
    with path.open(encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file)
    return ModelConfiguration.model_validate(_expand_environment(raw))
