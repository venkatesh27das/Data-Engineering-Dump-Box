"""Optional read-only SFTP boundary; disabled until an approved adapter is bound."""

from typing import Any


class SFTPConnector:
    source_type = "SFTP"
    enabled = False

    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter

    def __getattr__(self, name: str) -> Any:
        if not self.enabled or self.adapter is None:
            raise RuntimeError(
                "SFTP is disabled; configure host-key-pinned credential-provider adapter"
            )
        return getattr(self.adapter, name)
