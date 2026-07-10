import hashlib
import json
from typing import Any


def idempotency_key(scope: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{scope}:{serialized}".encode()).hexdigest()
