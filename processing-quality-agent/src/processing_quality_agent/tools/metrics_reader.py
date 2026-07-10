from __future__ import annotations

from typing import Protocol


class MetricsRepository(Protocol):
    async def parser_metrics(self, parser_ids: list[str]) -> list[dict[str, float | str]]: ...


class MetricsReader:
    name = "get_parser_metrics"
    description = "READ ONLY: aggregate governed historical parser quality, success, latency, cost, and stability metrics."
    state_changing = False

    def __init__(self, repository: MetricsRepository) -> None:
        self.repository = repository

    async def invoke(self, parser_ids: list[str]) -> list[dict[str, float | str]]:
        return await self.repository.parser_metrics(parser_ids)
