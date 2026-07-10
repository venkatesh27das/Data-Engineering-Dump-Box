from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .document import DocumentContext, SilverDocument, SilverElement


class ParserStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class EligibilityResult(BaseModel):
    eligible: bool
    reasons: list[str] = Field(default_factory=list)


class ParserRequest(BaseModel):
    document_id: str
    source_file_uri: str
    parser_config: dict[str, Any] = Field(default_factory=dict)
    source_bytes: bytes | None = Field(default=None, exclude=True)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class CostEstimate(BaseModel):
    amount: float = Field(ge=0)
    currency: str = "USD"
    basis: str = "estimate"


class HealthStatus(BaseModel):
    healthy: bool
    detail: str = ""


class ParserResult(BaseModel):
    parser_id: str
    parser_version: str = "unknown"
    status: ParserStatus
    document: SilverDocument | None = None
    elements: list[SilverElement] = Field(default_factory=list)
    latency_ms: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


class ParserAdapter(Protocol):
    parser_id: str

    def is_eligible(self, document: DocumentContext) -> EligibilityResult: ...
    async def parse(self, request: ParserRequest) -> ParserResult: ...
    def estimate_cost(self, request: ParserRequest) -> CostEstimate: ...
    async def health_check(self) -> HealthStatus: ...
