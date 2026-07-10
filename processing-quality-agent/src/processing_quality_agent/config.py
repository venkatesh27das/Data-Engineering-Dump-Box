from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TableMappings(BaseModel):
    bronze_manifest: str = "bronze_file_manifest"
    parser_run: str = "parser_run"
    silver_document: str = "silver_document_output"
    silver_element: str = "silver_element_output"
    quality_assessment: str = "quality_assessment"
    recovery_attempt: str = "recovery_attempt"
    parser_benchmark: str = "parser_benchmark"
    review_queue: str = "human_review_queue"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "local"
    use_mock_tools: bool = True
    dry_run_default: bool = True
    log_level: str = "INFO"
    databricks_host: str | None = None
    databricks_catalog: str = "main"
    databricks_bronze_schema: str = "bronze"
    databricks_silver_schema: str = "silver"
    databricks_operations_schema: str = "operations"
    databricks_workflow_job_ids: dict[str, int] = Field(default_factory=dict)
    databricks_model_endpoint: str | None = None
    mlflow_experiment: str = "/Shared/processing-quality-agent"
    azure_document_intelligence_endpoint: str | None = None
    azure_document_intelligence_auth_mode: str = "managed_identity"
    azure_document_intelligence_api_key: str | None = Field(default=None, repr=False)
    azure_document_intelligence_allow_api_key: bool = False
    azure_document_intelligence_model_id: str = "prebuilt-layout"
    azure_document_intelligence_timeout_seconds: int = 120
    custom_parser_url: str | None = None
    custom_parser_enabled: bool = False
    allowed_source_prefixes: list[str] = Field(default_factory=lambda: ["abfss://", "/Volumes/"])
    source_sample_max_bytes: int = Field(default=65536, ge=1, le=1048576)
    maximum_automatic_retries_per_parser: int = 1
    maximum_total_parser_attempts: int = 3
    quality_policy_file: Path = Path("resources/sample_quality_policy.yaml")
    routing_policy_file: Path = Path("resources/sample_routing_policy.yaml")
    table_mappings: TableMappings = Field(default_factory=TableMappings)

    @field_validator("databricks_workflow_job_ids", mode="before")
    @classmethod
    def parse_job_ids(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
