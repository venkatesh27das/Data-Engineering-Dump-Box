from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/workbook_agent.db"
    storage_root: Path = Path("./data/storage")
    max_upload_mb: int = 200
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    llm_reasoning_model: str = ""
    llm_vision_model: str = ""
    embedding_model: str = ""
    llm_request_timeout_seconds: int = 120
    llm_max_retries: int = 1
    enable_vision: bool = True
    enable_ocr: bool = True
    enable_embeddings: bool = True
    enable_entity_extraction: bool = True
    enable_graph_assets: bool = True
    auto_select_models: bool = True
    embedding_batch_size: int = 32
    embedding_max_chunks: int = 500
    vision_max_images: int = 12
    ocr_max_images: int = 12
    chart_max_items: int = 20

    @property
    def database_path(self) -> Path:
        raw = self.database_url.removeprefix("sqlite:///")
        return Path(raw).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
