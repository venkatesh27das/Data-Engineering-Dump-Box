"""Connector protocol. Implementations must never mutate source data."""

from typing import Protocol

from source_readiness_agent.models.contracts import (
    ConnectionValidationResult,
    SampleReadRequest,
    SourceDefinition,
    SourceInventoryEstimate,
    SourceListRequest,
    SourceObject,
    SourceObjectMetadata,
    SourceSample,
)


class SourceConnector(Protocol):
    source_type: str

    async def validate_connection(self, source: SourceDefinition) -> ConnectionValidationResult: ...
    async def list_objects(self, request: SourceListRequest) -> list[SourceObject]: ...
    async def read_metadata(self, source_object: SourceObject) -> SourceObjectMetadata: ...
    async def read_sample(self, request: SampleReadRequest) -> SourceSample: ...
    async def estimate_inventory(self, source: SourceDefinition) -> SourceInventoryEstimate: ...
