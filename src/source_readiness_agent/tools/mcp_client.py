"""MCP discovery/invocation boundary; unit tests use the in-memory implementation."""

from typing import Any, Protocol, cast


class MCPClient(Protocol):
    async def discover_tools(self) -> list[dict[str, Any]]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class MockMCPClient:
    def __init__(self, handlers: dict[str, Any] | None = None) -> None:
        self.handlers = handlers or {}

    async def discover_tools(self) -> list[dict[str, Any]]:
        return [{"name": name, "mutating": False} for name in self.handlers]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.handlers:
            raise KeyError(name)
        value = self.handlers[name](arguments)
        result = await value if hasattr(value, "__await__") else value
        return cast(dict[str, Any], result)
