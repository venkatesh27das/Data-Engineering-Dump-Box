from __future__ import annotations

import hashlib
import json
from typing import Any


def idempotency_key(
    operation: str,
    document_id: str,
    source_run_id: str,
    parser_id: str | None,
    parser_config: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "operation": operation,
            "document_id": document_id,
            "source_run_id": source_run_id,
            "parser_id": parser_id,
            "parser_config": parser_config,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def reject_arbitrary_sql(sql: str) -> None:
    raise PermissionError(
        "agent-generated SQL is prohibited; use a registered parameterized query or UC function"
    )
