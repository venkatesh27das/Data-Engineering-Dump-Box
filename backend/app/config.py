from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Knowledge Graph Builder"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    frontend_origins: str = "http://localhost:5173"

    ai_provider: Literal["lmstudio", "openai_compatible"] = "lmstudio"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_orchestrator_model: str = ""
    lmstudio_knowledge_model: str = ""
    lmstudio_embedding_model: str = ""
    lmstudio_timeout_seconds: float = 120
    lmstudio_connect_timeout_seconds: float = 10
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_orchestrator_model: str = ""
    openai_compatible_knowledge_model: str = ""
    openai_compatible_embedding_model: str = ""
    openai_compatible_timeout_seconds: float = 120
    openai_compatible_connect_timeout_seconds: float = 10
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    artifact_dir: str = "./data/artifacts"
    low_confidence_threshold: float = 0.80
    auto_approve_threshold: float = 0.95
    max_upload_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def repository_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def model_provider_name(self) -> str:
        return "AI Gateway" if self.ai_provider == "openai_compatible" else "LM Studio"

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.repository_root / path).resolve()

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only sqlite:/// database URLs are supported in the POC")
        return self.resolve_path(self.database_url.removeprefix(prefix))

    @property
    def upload_path(self) -> Path:
        return self.resolve_path(self.upload_dir)

    @property
    def artifact_path(self) -> Path:
        return self.resolve_path(self.artifact_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
