from pathlib import Path

from pydantic import Field, model_validator
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
    region_agent_threshold: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="after")
    def paths(self):
        for field, suffix in (
            ("upload_dir", "uploads"),
            ("output_dir", "outputs"),
            ("duckdb_path", "excel_intelligence.duckdb"),
            ("sqlite_path", "runs.sqlite"),
        ):
            setattr(self, field, (getattr(self, field) or self.data_dir / suffix).resolve())
        return self

    def prepare(self) -> None:
        for path in (self.upload_dir, self.output_dir, self.sqlite_path.parent, self.duckdb_path.parent):
            path.mkdir(parents=True, exist_ok=True)
