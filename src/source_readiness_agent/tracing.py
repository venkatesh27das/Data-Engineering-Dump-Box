"""Small MLflow tracing facade that degrades safely in local mode."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    try:
        import mlflow

        with mlflow.start_span(name=name) as span:
            for key, value in (attributes or {}).items():
                if not any(
                    secret in key.lower()
                    for secret in ("token", "secret", "password", "key", "content")
                ):
                    span.set_attribute(key, value)
            yield
    except ImportError:
        yield
