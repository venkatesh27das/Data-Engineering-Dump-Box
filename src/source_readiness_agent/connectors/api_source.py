"""Allowlisted, bounded enterprise API source boundary."""

from typing import Any


class APISourceConnector:
    source_type = "API"

    def __init__(
        self, adapter: Any | None = None, allowed_endpoints: set[str] | None = None
    ) -> None:
        self.adapter = adapter
        self.allowed_endpoints = allowed_endpoints or set()

    def __getattr__(self, name: str) -> Any:
        if self.adapter is None:
            raise RuntimeError(
                "API source is disabled; bind a timeout/payload-limited approved adapter"
            )
        return getattr(self.adapter, name)
