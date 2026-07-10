"""Runtime configuration loaded only from environment and policy resources."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "local"
    use_mock_tools: bool = True
    activation_enabled: bool = False
    default_sample_size: int = Field(default=25, ge=1, le=1000)
    maximum_sample_bytes: int = Field(default=524_288_000, ge=1)
    maximum_individual_file_bytes: int = Field(default=104_857_600, ge=1)
    maximum_listing_objects: int = Field(default=1000, ge=1, le=10_000)
    operation_timeout_seconds: int = Field(default=120, ge=1)
    source_allowlist_json: str = '["mock://", "file:///tmp/source-readiness-fixtures/"]'
    databricks_host: str | None = None
    databricks_catalog: str = "configured_catalog"
    databricks_configuration_schema: str = "source_configuration"
    databricks_bronze_schema: str = "bronze"
    databricks_operations_schema: str = "source_operations"
    databricks_workflow_job_id: int | None = None
    databricks_model_endpoint: str | None = None
    mlflow_experiment: str | None = None
    azure_adls_account_references_json: str = "[]"
    azure_approved_containers_json: str = "[]"
    azure_adf_subscription_reference: str | None = None
    azure_adf_resource_group_reference: str | None = None
    azure_adf_factory_reference: str | None = None
    azure_approved_adf_pipelines_json: str = "[]"
    resource_directory: Path = Path("resources")

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        value = value.lower()
        if value not in {"local", "dev", "test", "prod"}:
            raise ValueError("APP_ENV must be local, dev, test, or prod")
        return value

    @staticmethod
    def _json_list(value: str) -> list[str]:
        parsed = json.loads(value)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("expected a JSON array of strings")
        return parsed

    @property
    def source_allowlist(self) -> list[str]:
        return self._json_list(self.source_allowlist_json)

    @property
    def approved_adf_pipelines(self) -> list[str]:
        return self._json_list(self.azure_approved_adf_pipelines_json)

    def load_yaml(self, name: str) -> dict[str, Any]:
        path = self.resource_directory / name
        with path.open(encoding="utf-8") as handle:
            value = yaml.safe_load(handle) or {}
        if not isinstance(value, dict):
            raise ValueError(f"{path} must contain a mapping")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
