"""Explicit tool registry; arbitrary SQL/code tools cannot be registered."""

from .base import GovernedTool


class ToolRegistry:
    FORBIDDEN = {"execute_sql", "arbitrary_sql", "execute_python", "shell"}

    def __init__(self) -> None:
        self._tools: dict[str, GovernedTool] = {}

    def register(self, tool: GovernedTool) -> None:
        if tool.descriptor.name.lower() in self.FORBIDDEN:
            raise ValueError("arbitrary SQL, Python, and shell tools are prohibited")
        self._tools[tool.descriptor.name] = tool

    def get(self, name: str) -> GovernedTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown governed tool: {name}") from exc

    def inventory(self) -> list[dict[str, object]]:
        return [
            {
                "name": item.descriptor.name,
                "mutating": item.descriptor.mutating,
                "approval_required": item.descriptor.approval_required,
            }
            for item in self._tools.values()
        ]
