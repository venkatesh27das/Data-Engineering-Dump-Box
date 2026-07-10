from __future__ import annotations

import asyncio
import time
from typing import Any

from processing_quality_agent.models.document import DocumentContext, SilverDocument, SilverElement
from processing_quality_agent.models.parser import (
    CostEstimate,
    EligibilityResult,
    HealthStatus,
    ParserRequest,
    ParserResult,
    ParserStatus,
)


class AzureDocumentIntelligenceAdapter:
    parser_id = "azure_document_intelligence"

    def __init__(
        self,
        endpoint: str | None,
        model_id: str = "prebuilt-layout",
        *,
        allow_api_key: bool = False,
        api_key: str | None = None,
    ) -> None:
        self.endpoint, self.model_id, self.allow_api_key, self._api_key = (
            endpoint,
            model_id,
            allow_api_key,
            api_key,
        )
        self._client: Any = None

    def _client_instance(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.endpoint:
            raise ValueError("Azure Document Intelligence endpoint is not configured")
        from azure.ai.documentintelligence import DocumentIntelligenceClient

        if self.allow_api_key and self._api_key:
            from azure.core.credentials import AzureKeyCredential

            credential: Any = AzureKeyCredential(self._api_key)
        else:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
        self._client = DocumentIntelligenceClient(endpoint=self.endpoint, credential=credential)
        return self._client

    def is_eligible(self, document: DocumentContext) -> EligibilityResult:
        return EligibilityResult(
            eligible=document.manifest.mime_type
            in {"application/pdf", "image/tiff", "image/png", "image/jpeg"}
        )

    def estimate_cost(self, request: ParserRequest) -> CostEstimate:
        return CostEstimate(amount=0.05, basis="placeholder; configure Azure pricing model")

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            healthy=bool(self.endpoint),
            detail="endpoint configured" if self.endpoint else "endpoint missing",
        )

    async def parse(self, request: ParserRequest) -> ParserResult:
        started = time.monotonic()
        try:
            client = self._client_instance()
            source = request.source_bytes or {"urlSource": request.source_file_uri}
            poller = await asyncio.to_thread(
                client.begin_analyze_document, self.model_id, body=source
            )
            result = await asyncio.wait_for(
                asyncio.to_thread(poller.result), timeout=request.timeout_seconds
            )
            return self.normalize_result(request, result, int((time.monotonic() - started) * 1000))
        except TimeoutError:
            return ParserResult(
                parser_id=self.parser_id,
                status=ParserStatus.TIMEOUT,
                error_code="PARSER_TIMEOUT",
                error_message="Azure analysis timed out",
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            code = "PARSER_RATE_LIMIT" if status == 429 else "PARSER_SERVICE_ERROR"
            return ParserResult(
                parser_id=self.parser_id,
                status=ParserStatus.FAILED,
                error_code=code,
                error_message=str(exc)[:500],
            )

    def normalize_result(
        self, request: ParserRequest, result: Any, latency_ms: int = 0
    ) -> ParserResult:
        pages: list[Any] = list(getattr(result, "pages", []) or [])
        elements: list[SilverElement] = []
        text: list[str] = []
        refs: list[str] = []
        for page in pages:
            page_no = int(getattr(page, "page_number", len(refs) + 1))
            refs.append(f"page:{page_no}")
            for index, line in enumerate(getattr(page, "lines", []) or []):
                content = getattr(line, "content", "")
                text.append(content)
                polygon = [
                    float(value)
                    for point in (getattr(line, "polygon", []) or [])
                    for value in ((getattr(point, "x", 0), getattr(point, "y", 0)))
                ]
                elements.append(
                    SilverElement(
                        document_id=request.document_id,
                        run_id="pending",
                        page_number=page_no,
                        element_id=f"p{page_no}-l{index}",
                        element_type="line",
                        text=content,
                        bounding_box=polygon,
                    )
                )
        tables = []
        for table in getattr(result, "tables", []) or []:
            tables.append(
                {
                    "row_count": getattr(table, "row_count", 0),
                    "column_count": getattr(table, "column_count", 0),
                    "cells": [
                        {
                            "row_index": getattr(cell, "row_index", 0),
                            "column_index": getattr(cell, "column_index", 0),
                            "content": getattr(cell, "content", ""),
                        }
                        for cell in getattr(table, "cells", []) or []
                    ],
                }
            )
        doc = SilverDocument(
            document_id=request.document_id,
            run_id="pending",
            normalized_text="\n".join(text),
            page_count=len(pages),
            extracted_page_count=len(pages),
            table_payload=tables,
            source_references=refs,
        )
        return ParserResult(
            parser_id=self.parser_id,
            parser_version=self.model_id,
            status=ParserStatus.SUCCEEDED,
            document=doc,
            elements=elements,
            latency_ms=latency_ms,
            estimated_cost=self.estimate_cost(request).amount,
        )
