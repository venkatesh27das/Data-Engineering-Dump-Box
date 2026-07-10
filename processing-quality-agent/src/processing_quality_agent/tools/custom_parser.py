from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.parser import (
    CostEstimate,
    EligibilityResult,
    HealthStatus,
    ParserRequest,
    ParserResult,
)


class CustomParserAdapter:
    parser_id = "custom_parser"

    def __init__(
        self,
        *,
        enabled: bool = False,
        url: str | None = None,
        callable_parser: Callable[[ParserRequest], Any] | None = None,
    ) -> None:
        self.enabled, self.url, self.callable_parser = enabled, url, callable_parser

    def is_eligible(self, document: DocumentContext) -> EligibilityResult:
        return EligibilityResult(
            eligible=self.enabled, reasons=[] if self.enabled else ["adapter disabled"]
        )

    def estimate_cost(self, request: ParserRequest) -> CostEstimate:
        return CostEstimate(amount=0, basis="custom parser pricing not configured")

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            healthy=self.enabled and bool(self.url or self.callable_parser),
            detail="disabled or unconfigured" if not self.enabled else "configured",
        )

    async def parse(self, request: ParserRequest) -> ParserResult:
        if not self.enabled:
            raise RuntimeError("custom parser is disabled")
        if self.callable_parser:
            value = self.callable_parser(request)
            return ParserResult.model_validate(value)
        if not self.url:
            raise RuntimeError("custom parser URL is missing")
        async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
            response = await client.post(
                self.url, json=request.model_dump(exclude={"source_bytes"})
            )
            response.raise_for_status()
            return ParserResult.model_validate(response.json())
