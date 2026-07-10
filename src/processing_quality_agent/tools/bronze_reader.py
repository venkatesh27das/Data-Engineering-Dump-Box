from __future__ import annotations

from typing import Protocol

from processing_quality_agent.models.document import BronzeManifest, DocumentContext


class DocumentRepository(Protocol):
    async def get_document_context(
        self, document_id: str, run_id: str | None = None
    ) -> DocumentContext: ...
    async def get_bronze_manifest(self, document_id: str) -> BronzeManifest: ...


class BronzeReader:
    name = "get_document_context"
    description = "READ ONLY: retrieve governed Bronze manifest and related processing context by document ID."
    state_changing = False

    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    async def invoke(self, document_id: str, run_id: str | None = None) -> DocumentContext:
        return await self.repository.get_document_context(document_id, run_id)
