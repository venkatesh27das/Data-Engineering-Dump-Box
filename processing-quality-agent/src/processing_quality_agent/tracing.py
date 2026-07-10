from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def _safe_attributes(request: Any) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for key in ("document_id", "run_id", "source_run_id", "correlation_id", "actor"):
        value = getattr(request, key, None)
        if value:
            attributes[key] = str(value)
    attributes["operation_mode"] = request.__class__.__name__.removesuffix("Request").upper()
    return attributes


@asynccontextmanager
async def trace_span(name: str, attributes: dict[str, str] | None = None) -> AsyncIterator[None]:
    """Create an MLflow span when available, otherwise remain a safe local no-op."""
    try:
        import mlflow

        span_context = mlflow.start_span(name=name)
    except Exception:
        yield
        return
    with span_context as span:
        for key, value in (attributes or {}).items():
            span.set_attribute(key, value)
        yield


def traced_operation(
    name: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorator(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(function)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request = args[1] if len(args) > 1 else kwargs.get("request")
            async with trace_span(name, _safe_attributes(request)):
                return await function(*args, **kwargs)

        return wrapper

    return decorator
