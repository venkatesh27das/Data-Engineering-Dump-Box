from __future__ import annotations

from typing import Protocol

from processing_quality_agent.models.document import ParserRun
from processing_quality_agent.models.quality import QualityAssessment


class HistoryRepository(Protocol):
    async def get_parser_history(self, document_id: str) -> list[ParserRun]: ...
    async def get_quality_assessment(
        self, document_id: str, run_id: str
    ) -> QualityAssessment | None: ...


class ParserHistoryReader:
    name = "get_parser_history"
    description = "READ ONLY: retrieve immutable parser attempt history for retry-loop prevention and diagnosis."
    state_changing = False

    def __init__(self, repository: HistoryRepository) -> None:
        self.repository = repository

    async def invoke(self, document_id: str) -> list[ParserRun]:
        return await self.repository.get_parser_history(document_id)
