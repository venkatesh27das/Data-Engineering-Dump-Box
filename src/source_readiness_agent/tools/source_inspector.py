"""Bounded connector inspection facade."""

from source_readiness_agent.connectors.base import SourceConnector
from source_readiness_agent.models.contracts import (
    ConnectionValidationResult,
    SourceDefinition,
    SourceInventoryEstimate,
    SourceListRequest,
    SourceObject,
)


class SourceInspector:
    def __init__(self, connector: SourceConnector, maximum_objects: int = 1000) -> None:
        self.connector = connector
        self.maximum_objects = maximum_objects

    async def inspect(
        self, source: SourceDefinition
    ) -> tuple[ConnectionValidationResult, list[SourceObject], SourceInventoryEstimate | None]:
        access = await self.connector.validate_connection(source)
        if not access.accessible or not access.allowed:
            return (
                access,
                [],
                await self.connector.estimate_inventory(source) if access.accessible else None,
            )
        objects = await self.connector.list_objects(
            SourceListRequest(source=source, maximum_objects=self.maximum_objects)
        )
        inventory = await self.connector.estimate_inventory(source)
        return access, objects, inventory
