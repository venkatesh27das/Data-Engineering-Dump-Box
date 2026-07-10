"""Structured logging and defense-in-depth secret redaction."""

import json
import logging
import re
from typing import Any

SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]+|(?:token|secret|password|account_key)\s*[=:]\s*[^\s,;]+)"
)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(x in key.lower() for x in ("token", "secret", "password", "key"))
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            redact(
                {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
            ),
            default=str,
        )


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
