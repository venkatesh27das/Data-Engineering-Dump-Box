import json
from io import BytesIO

import openpyxl

from app.agents.workbook_agent import AgentResult
from app.services.run_service import RunService
from app.storage.vector_store import VectorStore


def ambiguous_upload(service):
    wb = openpyxl.Workbook()
    wb.active.append([1, 2])
    wb.active.append([3, 4])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return service.upload(stream, "ambiguous.xlsx")


def test_agent_remediation_and_offline(settings, monkeypatch):
    from app.agents.workbook_agent import WorkbookAgent
    from app.llm.lmstudio_client import LMStudioClient

    settings.llm_model = "mock-local"
    settings.enable_summaries = False
    monkeypatch.setattr(LMStudioClient, "health_check", lambda self: {"available": True})
    called = []

    def review(self, feedback=""):
        called.append(self.tools.region.range)
        return AgentResult(
            region_id=self.tools.region.region_id,
            classification="kpi_block",
            confidence=0.9,
            reason_summary="Numeric block",
            recommended_processing="key values",
            requires_human_review=False,
        )

    monkeypatch.setattr(WorkbookAgent, "review", review)
    service = RunService(settings)
    record = ambiguous_upload(service)
    run = service.process(record.workbook_id)
    assert run.stage != "FAILED", run.error
    assert called == ["A1:B2"]
    output = settings.output_dir / run.run_id
    regions = json.loads((output / "metadata/regions.json").read_text())
    assert regions[0]["agent_review_status"] == "reviewed"
    tables = json.loads((output / "metadata/table_assets.json").read_text())
    assert tables[0]["source_rows"] == [1, 2]
    monkeypatch.setattr(LMStudioClient, "health_check", lambda self: {"available": False})
    other = service.process(record.workbook_id)
    assert other.stage == "COMPLETED_WITH_WARNINGS"
    assert len(called) == 1


def test_vectors_and_semantic_assets(settings, samples, monkeypatch):
    from app.llm.lmstudio_client import LMStudioClient

    settings.embedding_model = "mock-embedding"
    monkeypatch.setattr(LMStudioClient, "health_check", lambda self: {"available": True})
    monkeypatch.setattr(LMStudioClient, "embedding", lambda self, texts: [[1.0, 0.0, 0.5] for text in texts])
    service = RunService(settings)
    with samples["fixture_multi_region"].open("rb") as source:
        record = service.upload(source, "text.xlsx")
    run = service.process(record.workbook_id)
    assert run.stage != "FAILED", run.error
    results = VectorStore(settings.lancedb_path).search(
        [1.0, 0.0, 0.5], settings.embedding_model, run_id=run.run_id
    )
    assert results
    assert all(r["workbook_id"] == record.workbook_id for r in results)
    assert any(r["asset_type"] == "narrative" for r in results)
    texts = [
        json.loads(line)
        for line in (settings.output_dir / run.run_id / "text/text_assets.jsonl").read_text().splitlines()
    ]
    assert all(t["embedding_status"] == "embedded" for t in texts)
    assert VectorStore(settings.lancedb_path).search([1.0, 0.0], "different-model") == []


def test_visual_assets_and_quality(settings, samples):
    service = RunService(settings)
    with samples["fixture_complex"].open("rb") as source:
        record = service.upload(source, "complex.xlsx")
    run = service.process(record.workbook_id)
    output = settings.output_dir / run.run_id
    images = json.loads((output / "metadata/images.json").read_text())
    charts = json.loads((output / "metadata/charts.json").read_text())
    assert len(images) == len(charts) == 1
    assert (output / images[0]["filename"]).read_bytes().startswith(b"\x89PNG")
    assert charts[0]["title"] == "Synthetic values"
    assert any("B" in reference for reference in charts[0]["referenced_ranges"])
    quality = json.loads((output / "quality/quality_report.json").read_text())
    assert 0 < quality["overall_quality_score"] <= 1
    assert quality["components"]["visual_processing_score"] == 1


def test_duckdb_migrates_phase_one_schema(settings, samples):
    import duckdb

    settings.prepare()
    with duckdb.connect(str(settings.duckdb_path)) as database:
        database.execute("CREATE TABLE workbooks (run_id VARCHAR, ordinal INTEGER, payload JSON)")
    service = RunService(settings)
    with samples["fixture_simple"].open("rb") as source:
        record = service.upload(source, "simple.xlsx")
    run = service.process(record.workbook_id)
    assert run.stage != "FAILED", run.error
    with duckdb.connect(str(settings.duckdb_path)) as database:
        row = database.execute(
            "SELECT filename, formula_count FROM workbooks WHERE run_id = ?", [run.run_id]
        ).fetchone()
    assert row == ("simple.xlsx", 3)
