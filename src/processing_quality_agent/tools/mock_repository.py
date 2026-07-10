from __future__ import annotations

from copy import deepcopy
from typing import Any

from processing_quality_agent.models.document import (
    BronzeManifest,
    DocumentContext,
    ParserRun,
    SilverDocument,
    SilverElement,
)
from processing_quality_agent.models.quality import QualityAssessment


def default_contexts() -> dict[str, DocumentContext]:
    manifest = BronzeManifest(
        document_id="DOC-102",
        bronze_manifest_id="BM-102",
        source_file_uri="abfss://landing@example.dfs.core.windows.net/bronze/DOC-102.pdf",
        source_system="sharepoint",
        source_metadata={"tables_expected": True},
        file_name="policy.pdf",
        file_type="pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        file_hash="synthetic-sha256",
        ingestion_batch_id="BATCH-55",
        processing_status="QUALITY_FAILED",
        current_run_id="RUN-101",
    )
    run = ParserRun(
        run_id="RUN-101",
        document_id="DOC-102",
        parser_id="databricks_primary",
        parser_version="mock-1",
        status="SUCCEEDED",
        latency_ms=900,
        estimated_cost=0.01,
        warnings=["table expected but absent"],
    )
    doc = SilverDocument(
        document_id="DOC-102",
        run_id="RUN-101",
        normalized_text="Policy document with readable text. " * 30,
        page_count=3,
        extracted_page_count=3,
        parser_confidence=0.93,
        source_references=["page:1", "page:2", "page:3"],
    )
    elements = [
        SilverElement(
            document_id="DOC-102",
            run_id="RUN-101",
            page_number=i,
            element_id=f"e-{i}",
            element_type="paragraph",
            text="Synthetic page",
            bounding_box=[0, 0, 1, 1],
            confidence=0.9,
            source_reference=f"page:{i}",
        )
        for i in range(1, 4)
    ]
    return {
        "DOC-102": DocumentContext(
            manifest=manifest,
            parser_run=run,
            silver_document=doc,
            silver_elements=elements,
            document_class="scanned_policy_pdf",
        )
    }


class InMemoryRepository:
    def __init__(self, contexts: dict[str, DocumentContext] | None = None) -> None:
        self.contexts = contexts or default_contexts()
        self.assessments: dict[tuple[str, str], QualityAssessment] = {}
        self.operations: dict[str, dict[str, Any]] = {}
        self.history: dict[str, list[ParserRun]] = {
            key: [value.parser_run] if value.parser_run else []
            for key, value in self.contexts.items()
        }

    async def get_document_context(
        self, document_id: str, run_id: str | None = None
    ) -> DocumentContext:
        if document_id not in self.contexts:
            raise KeyError(f"document not found: {document_id}")
        context = deepcopy(self.contexts[document_id])
        current_run_id = context.parser_run.run_id if context.parser_run else None
        if not run_id or run_id == current_run_id:
            return context
        if not run_id.startswith("mock-run-"):
            raise KeyError(f"parser run not found: {run_id}")

        # Local mock mode materializes a new immutable parser-output version after a
        # successful workflow. It intentionally leaves the source manifest untouched.
        parser_id = "azure_document_intelligence"
        context.parser_run = ParserRun(
            run_id=run_id,
            document_id=document_id,
            parser_id=parser_id,
            parser_version="mock-recovery-1",
            status="SUCCEEDED",
            latency_ms=1100,
            estimated_cost=0.05,
        )
        if context.silver_document:
            context.silver_document.run_id = run_id
            context.silver_document.parser_confidence = 0.96
            if context.manifest.source_metadata.get("tables_expected"):
                context.silver_document.table_payload = [
                    {
                        "row_count": 2,
                        "column_count": 2,
                        "cells": [
                            {"row_index": 0, "column_index": 0, "content": "Policy"},
                            {"row_index": 0, "column_index": 1, "content": "Value"},
                        ],
                    }
                ]
        for element in context.silver_elements:
            element.run_id = run_id
        context.manifest.current_run_id = run_id
        context.manifest.processing_status = "RECOVERY_SUCCEEDED"
        if all(item.run_id != run_id for item in self.history.setdefault(document_id, [])):
            self.history[document_id].append(deepcopy(context.parser_run))
        return context

    async def get_bronze_manifest(self, document_id: str) -> BronzeManifest:
        return (await self.get_document_context(document_id)).manifest

    async def get_parser_history(self, document_id: str) -> list[ParserRun]:
        return deepcopy(self.history.get(document_id, []))

    async def get_quality_assessment(
        self, document_id: str, run_id: str
    ) -> QualityAssessment | None:
        return deepcopy(self.assessments.get((document_id, run_id)))

    async def record_quality_assessment(self, assessment: QualityAssessment) -> None:
        self.assessments[(assessment.document_id, assessment.run_id)] = deepcopy(assessment)

    async def write_idempotent(
        self, operation: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        compound = f"{operation}:{key}"
        if compound in self.operations:
            return deepcopy(self.operations[compound])
        result = {
            "status": "COMPLETED",
            "operation": operation,
            "idempotency_key": key,
            "payload": deepcopy(payload),
        }
        self.operations[compound] = result
        return deepcopy(result)

    async def parser_metrics(self, parser_ids: list[str]) -> list[dict[str, float | str]]:
        defaults = {
            "databricks_primary": {
                "quality": 0.68,
                "success": 0.95,
                "latency": 0.90,
                "cost": 0.95,
                "stability": 0.90,
            },
            "azure_document_intelligence": {
                "quality": 0.92,
                "success": 0.92,
                "latency": 0.70,
                "cost": 0.65,
                "stability": 0.88,
            },
            "custom_parser": {
                "quality": 0.80,
                "success": 0.85,
                "latency": 0.80,
                "cost": 0.80,
                "stability": 0.75,
            },
        }
        return [
            {
                "parser_id": parser_id,
                **defaults.get(
                    parser_id,
                    {"quality": 0.5, "success": 0.5, "latency": 0.5, "cost": 0.5, "stability": 0.5},
                ),
            }
            for parser_id in parser_ids
        ]
