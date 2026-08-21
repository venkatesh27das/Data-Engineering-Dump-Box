import os

import httpx


base_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")
try:
    response = httpx.get(f"{base_url}/models", timeout=5)
    response.raise_for_status()
    models = [item["id"] for item in response.json().get("data", [])]
    print("LM Studio is reachable.")
    for model in models:
        print(f"- {model}")
except httpx.HTTPError as error:
    raise SystemExit(f"LM Studio is unavailable at {base_url}: {error}") from error

