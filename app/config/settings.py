from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    data_dir: Path = Path("data")
    upload_dir: Path | None = None
    output_dir: Path | None = None
    duckdb_path: Path | None = None
    sqlite_path: Path | None = None
    max_upload_mb: float = Field(default=100, gt=0)
    max_uncompressed_mb: float = Field(default=500, gt=0)
    max_sheet_cells: int = Field(default=2_000_000, gt=0)
    max_regions_per_sheet: int = Field(default=2000, gt=0)
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_api_key: str = "lm-studio"
    llm_model: str = ""
    vlm_model: str = ""
    embedding_model: str = ""
    enable_agent: bool = True
    enable_vlm: bool = True
    enable_embeddings: bool = True
    enable_libreoffice_render: bool = False
    enable_summaries: bool = True
    max_agent_steps: int = Field(default=8, ge=1, le=20)
    max_agent_regions: int = Field(default=20, ge=1, le=100)
    max_tool_cells: int = Field(default=200, ge=1, le=1000)
    lm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    render_timeout_seconds: float = Field(default=60, gt=0, le=300)
    max_render_pages: int = Field(default=20, ge=1, le=100)
    max_embedding_assets: int = Field(default=1000, ge=1)
    lancedb_path: Path | None = None
    region_agent_threshold: float = Field(default=0.7, ge=0, le=1)

    @field_validator("lm_studio_base_url")
    @classmethod
    def local_model_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("LM_STUDIO_BASE_URL must use a loopback address")
        return value

    @model_validator(mode="after")
    def paths(self):
        for field, suffix in (
            ("upload_dir", "uploads"),
            ("output_dir", "outputs"),
            ("duckdb_path", "excel_intelligence.duckdb"),
            ("sqlite_path", "runs.sqlite"),
            ("lancedb_path", "lancedb"),
        ):
            setattr(self, field, (getattr(self, field) or self.data_dir / suffix).resolve())
        return self

    def prepare(self) -> None:
        for path in (
            self.upload_dir,
            self.output_dir,
            self.sqlite_path.parent,
            self.duckdb_path.parent,
            self.lancedb_path,
        ):
            path.mkdir(parents=True, exist_ok=True)
