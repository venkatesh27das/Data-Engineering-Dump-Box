from __future__ import annotations

from pathlib import PurePosixPath

from processing_quality_agent.tools.base import UnsafeSourceURIError


class VolumeReader:
    name = "read_source_file_sample"
    description = (
        "READ ONLY: read a bounded sample from an allowlisted UC Volume or ADLS source URI."
    )
    state_changing = False

    def __init__(self, allowed_prefixes: list[str], max_bytes: int = 65536) -> None:
        self.allowed_prefixes, self.max_bytes = allowed_prefixes, max_bytes

    def validate_uri(self, uri: str) -> None:
        if not any(uri.startswith(prefix) for prefix in self.allowed_prefixes):
            raise UnsafeSourceURIError("source URI is outside configured allowlist")
        normalized = uri.replace("abfss://", "/")
        if ".." in PurePosixPath(normalized).parts:
            raise UnsafeSourceURIError("path traversal is not permitted")

    async def invoke(self, source_file_uri: str, requested_bytes: int = 4096) -> bytes:
        self.validate_uri(source_file_uri)
        limit = min(max(1, requested_bytes), self.max_bytes)
        if source_file_uri.startswith("/Volumes/"):
            with open(source_file_uri, "rb") as handle:
                return handle.read(limit)
        raise UnsafeSourceURIError("ADLS reads require a configured governed storage client")
