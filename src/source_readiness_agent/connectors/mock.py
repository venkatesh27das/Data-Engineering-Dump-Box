"""Fully functional, bounded local connector used by tests and local mode."""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path

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


class MockConnector:
    source_type = "MOCK"

    def __init__(self, root: Path, allowlist: list[str] | None = None) -> None:
        self.root = root.resolve()
        self.allowlist = allowlist or ["mock://", "file://"]

    def _resolve(self, source: SourceDefinition) -> Path:
        if source.source_location.startswith("mock://"):
            suffix = source.source_location.removeprefix("mock://").lstrip("/")
            candidate = (self.root / suffix).resolve()
        elif source.source_location.startswith("file://"):
            candidate = Path(source.source_location.removeprefix("file://")).resolve()
        else:
            raise ValueError("mock connector supports mock:// and file:// only")
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("source path is outside the configured fixture root")
        return candidate

    async def validate_connection(self, source: SourceDefinition) -> ConnectionValidationResult:
        allowed = any(source.source_location.startswith(prefix) for prefix in self.allowlist)
        try:
            path = self._resolve(source)
            accessible = path.is_dir()
        except ValueError:
            accessible = False
        issues = []
        if not allowed:
            issues.append("source path is outside allowlist")
        if not accessible:
            issues.append("source is inaccessible")
        return ConnectionValidationResult(
            accessible=accessible,
            allowed=allowed,
            permissions=["READ"] if accessible else [],
            issues=issues,
        )

    async def list_objects(self, request: SourceListRequest) -> list[SourceObject]:
        root = self._resolve(request.source)
        objects: list[SourceObject] = []
        # A single bounded directory walk is acceptable only for local fixtures.
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if len(objects) >= request.maximum_objects:
                break
            stat = path.stat()
            relative = path.relative_to(root).as_posix()
            digest = (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if stat.st_size <= 10_485_760
                else None
            )
            objects.append(
                SourceObject(
                    object_id=f"{request.source.source_id}:{relative}",
                    source_id=request.source.source_id,
                    path_or_uri=f"mock://{relative}",
                    file_name=path.name,
                    extension=path.suffix.lower().lstrip("."),
                    reported_mime_type=mimetypes.guess_type(path.name)[0],
                    file_size_bytes=stat.st_size,
                    last_modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                    checksum_if_available=digest,
                    source_metadata={"relative_path": relative, "fixture": True},
                )
            )
        return objects

    async def read_metadata(self, source_object: SourceObject) -> SourceObjectMetadata:
        return SourceObjectMetadata(
            object_id=source_object.object_id, values=source_object.source_metadata
        )

    async def read_sample(self, request: SampleReadRequest) -> SourceSample:
        relative = request.source_object.source_metadata.get("relative_path")
        if not isinstance(relative, str):
            raise ValueError("mock object is missing relative_path")
        path = (self.root / relative).resolve()
        if self.root not in path.parents:
            raise ValueError("sample path escapes fixture root")
        with path.open("rb") as handle:
            content = handle.read(request.maximum_bytes + 1)
        return SourceSample(
            object_id=request.source_object.object_id,
            content=content[: request.maximum_bytes],
            truncated=len(content) > request.maximum_bytes,
        )

    async def estimate_inventory(self, source: SourceDefinition) -> SourceInventoryEstimate:
        objects = await self.list_objects(SourceListRequest(source=source, maximum_objects=10_000))
        return SourceInventoryEstimate(
            estimated_file_count=len(objects),
            estimated_total_bytes=sum(item.file_size_bytes for item in objects),
            complete=len(objects) < 10_000,
        )
