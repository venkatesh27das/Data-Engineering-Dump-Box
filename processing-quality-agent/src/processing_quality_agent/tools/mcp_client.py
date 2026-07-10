from __future__ import annotations

from typing import Any, Protocol


class MCPClient(Protocol):
    async def discover_tools(self) -> list[dict[str, Any]]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class DisabledMCPClient:
    async def discover_tools(self) -> list[dict[str, Any]]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError("MCP is not configured")
