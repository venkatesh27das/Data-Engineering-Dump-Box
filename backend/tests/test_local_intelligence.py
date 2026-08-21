import json
from pathlib import Path

import httpx

from app.agents.deepagents_runtime import DeepAgentsRuntime
from app.agents.schemas import OCRExtraction, ValidationSummary, VisualInterpretation
from app.core.config import Settings
from app.llm.lmstudio_client import LMStudioClient
from app.llm.model_registry import ModelRegistry
from app.processing.extractor import ExtractionResult


def _response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "http://local.test"))


def test_registry_auto_selects_loaded_model_roles(tmp_path: Path, monkeypatch):
    settings = Settings(storage_root=tmp_path / "storage")
    registry = ModelRegistry(settings)
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *_args, **_kwargs: _response(
            {
                "data": [
                    {"id": "google/gemma-4-12b"},
                    {"id": "qwen/qwen3.5-9b"},
                    {"id": "text-embedding-nomic-embed-text-v1.5"},
                ]
            }
        ),
    )

    status = registry.status()

    assert status["capability_check"] == "ready"
    assert status["reasoning_model"] == "qwen/qwen3.5-9b"
    assert status["vision_model"] == "google/gemma-4-12b"
    assert status["embedding_model"] == "text-embedding-nomic-embed-text-v1.5"
    assert status["roles"]["reasoning"]["selection"] == "auto"


def test_lmstudio_client_accepts_reasoning_content_and_embeddings(monkeypatch):
    settings = Settings(lm_studio_base_url="http://local.test/v1")
    client = LMStudioClient(settings)
    calls = 0

    def fake_post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "reasoning_content": json.dumps(
                                    {"status": "passed", "findings": [], "confidence": 1.0}
                                ),
                            }
                        }
                    ]
                }
            )
        return _response({"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    result = client.structured_chat("reasoning", ValidationSummary, "Return JSON", "Run a check")
    vectors = client.embeddings("embedding", ["workbook"])

    assert result.status == "passed"
    assert vectors == [[0.1, 0.2, 0.3]]


class _ReadyRegistry:
    def status(self):
        return {"reachable": True, "reasoning_model": "reasoning", "vision_model": "vision"}


class _OCRClient:
    def structured_chat(self, _model, schema, *_args, **_kwargs):
        if schema is VisualInterpretation:
            return VisualInterpretation(
                description="A text image",
                classification="document",
                extracted_text=[],
                confidence=0.9,
            )
        assert schema is OCRExtraction
        return OCRExtraction(full_text="INVOICE TOTAL 125000", language="en", confidence=0.99)


def test_visual_agent_runs_dedicated_ocr_recovery():
    settings = Settings(enable_vision=True, enable_ocr=True)
    runtime = DeepAgentsRuntime(settings, _ReadyRegistry(), _OCRClient())
    result = ExtractionResult(
        manifest={},
        media=[("image.png", b"image")],
        images=[
            {
                "image_id": "image.1",
                "sheet_name": "Invoice",
                "anchor_cell": "A1",
                "width": 100,
                "height": 50,
                "media_file": "image.png",
            }
        ],
        assets=[
            {
                "id": "image.1",
                "summary": "",
                "confidence": 0.5,
                "review_status": "open",
            }
        ],
    )
    report = {"agents": {}}

    runtime._interpret_visuals(result, report, "vision")

    assert result.images[0]["extracted_text"] == ["INVOICE TOTAL 125000"]
    assert result.images[0]["ocr"]["status"] == "completed"
    assert report["agents"]["visual_agent"] == "interpreted:1"
