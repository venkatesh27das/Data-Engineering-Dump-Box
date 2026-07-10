from __future__ import annotations

from typing import Any, Protocol

from processing_quality_agent.tools.base import WriteContext


class OperationsRepository(Protocol):
    async def write_idempotent(
        self, operation: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class GovernedWriter:
    state_changing = True

    def __init__(self, name: str, description: str, repository: OperationsRepository) -> None:
        self.name, self.description, self.repository = (
            name,
            f"STATE CHANGING: {description}",
            repository,
        )

    async def invoke(
        self, *, write_context: WriteContext, idempotency_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        write_context.validate()
        if write_context.dry_run:
            return {"status": "DRY_RUN", "operation": self.name, "idempotency_key": idempotency_key}
        return await self.repository.write_idempotent(self.name, idempotency_key, payload)
