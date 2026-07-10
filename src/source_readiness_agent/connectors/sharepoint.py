"""Pluggable Microsoft Graph/enterprise SharePoint connector boundary."""

from typing import Any, Protocol

from .base import SourceConnector


class SharePointAuthenticationProvider(Protocol):
    async def get_authorization_headers(self) -> dict[str, str]: ...


class SharePointConnector(SourceConnector):
    source_type = "SHAREPOINT"

    def __init__(self, adapter: SourceConnector | None = None) -> None:
        self.adapter = adapter

    def __getattr__(self, name: str) -> Any:
        if self.adapter is None:
            raise RuntimeError("SharePoint is disabled; bind an approved Microsoft Graph adapter")
        return getattr(self.adapter, name)
