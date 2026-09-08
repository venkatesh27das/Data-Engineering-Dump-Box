import hashlib
import json
from pathlib import Path

import duckdb
import networkx as nx
import polars as pl
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.run_service import RunService


@pytest.mark.parametrize("fixture", ["simple", "multi_region", "cross_sheet", "complex"])
def test_end_to_end(samples, settings, fixture):
    sample = samples[f"fixture_{fixture}"]
    original = sample.read_bytes()
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["agents_enabled"] is False
        response = client.post("/workbooks/upload", files={"file": (sample.name, original)})
        assert response.status_code == 201, response.text
        workbook = response.json()
        wid = workbook["workbook_id"]
        assert client.get(f"/workbooks/{wid}/tables").status_code == 409
        run = client.post(f"/workbooks/{wid}/process").json()
        assert run["stage"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS"), run
        assert client.get(f"/runs/{run['run_id']}/status").json()["stage"] == run["stage"]
        output = settings.output_dir / run["run_id"]
        manifest = json.loads((output / "manifest.json").read_text())
        expected = {
            "simple": {"sheets": 2, "tables": 1, "formulas": 3, "dependencies": 5},
            "multi_region": {"sheets": 1, "tables": 2, "formulas": 0, "dependencies": 0},
            "cross_sheet": {"sheets": 3, "tables": 1, "formulas": 2, "dependencies": 3},
            "complex": {"sheets": 5, "tables": 1, "formulas": 4, "dependencies": 5},
        }
        assert manifest["counts"] == expected[fixture]
        for asset in manifest["files"]:
            content = (output / asset["path"]).read_bytes()
            assert hashlib.sha256(content).hexdigest() == asset["sha256"]
        sheets = client.get(f"/workbooks/{wid}/sheets").json()
        assert len(sheets) == manifest["counts"]["sheets"]
        tables = client.get(f"/workbooks/{wid}/tables").json()
        if fixture == "multi_region":
            assert tables[0]["original_columns"] == ["Region", "Revenue"]
            assert tables[1]["original_columns"] == ["Category", "Target"]
        with duckdb.connect(str(settings.duckdb_path)) as db:
            assert (
                db.execute("SELECT count(*) FROM workbooks WHERE run_id=?", [run["run_id"]]).fetchone()[0]
                == 1
            )
            for table in tables:
                frame = pl.read_parquet(output / table["parquet_path"])
                assert frame.height == table["row_count"]
                assert (
                    db.execute(f'SELECT count(*) FROM "{table["duckdb_table"]}"').fetchone()[0]
                    == frame.height
                )
        formulas = client.get(f"/workbooks/{wid}/formulas").json()
        assert len(formulas) == manifest["counts"]["formulas"]
        graph = client.get(f"/workbooks/{wid}/graph").json()
        restored = nx.read_graphml(output / "graph/dependency_graph.graphml")
        assert len(restored) == len(graph["nodes"])
        assert sample.read_bytes() == original
        assert Path(workbook["file_path"]).read_bytes() == original
        old_manifest = (output / "manifest.json").read_bytes()
        second = client.post(f"/workbooks/{wid}/process").json()
        assert second["run_id"] != run["run_id"]
        assert second["stage"] == run["stage"]
        assert (output / "manifest.json").read_bytes() == old_manifest
    # Registry survives a new application/service instance.
    assert RunService(settings).metadata.run(run["run_id"]).stage == run["stage"]


def test_errors(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/runs/missing").status_code == 404
        assert client.post("/workbooks/missing/process").status_code == 404
        assert client.post("/workbooks/upload", files={"file": ("bad.xlsm", b"bad")}).status_code == 422
        assert client.post("/workbooks/upload", files={"file": ("bad.xlsx", b"bad")}).status_code == 422
        assert client.post("/search", json={"query": "summary"}).status_code == 503


def test_phase_five_api_assets(samples, settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["phase"] == 5
        status = client.get("/system/status")
        assert status.status_code == 200
        assert set(status.json()) == {
            "lm_studio",
            "libreoffice_available",
            "agent_configured",
            "vlm_configured",
            "embeddings_configured",
        }
        response = client.post(
            "/workbooks/upload",
            files={"file": ("complex.xlsx", samples["fixture_complex"].read_bytes())},
        )
        workbook_id = response.json()["workbook_id"]
        run = client.post(f"/workbooks/{workbook_id}/process").json()
        assert run["stage"] != "FAILED", run
        for endpoint in ("regions", "text", "images", "charts", "summaries"):
            response = client.get(f"/workbooks/{workbook_id}/{endpoint}")
            assert response.status_code == 200
            assert isinstance(response.json(), list)
        assert len(client.get(f"/workbooks/{workbook_id}/images").json()) == 1
        assert len(client.get(f"/workbooks/{workbook_id}/charts").json()) == 1
        assert client.get(f"/workbooks/{workbook_id}/summaries").json()


def test_failed_run(samples, settings):
    settings.max_sheet_cells = 1
    with TestClient(create_app(settings)) as client:
        wid = client.post(
            "/workbooks/upload", files={"file": ("simple.xlsx", samples["fixture_simple"].read_bytes())}
        ).json()["workbook_id"]
        run = client.post(f"/workbooks/{wid}/process").json()
        assert run["stage"] == "FAILED"
        assert "MAX_SHEET_CELLS" in run["error"]
        assert (settings.output_dir / run["run_id"] / "failure.json").exists()


def test_writer_busy(samples, settings):
    with TestClient(create_app(settings)) as client:
        wid = client.post(
            "/workbooks/upload", files={"file": ("simple.xlsx", samples["fixture_simple"].read_bytes())}
        ).json()["workbook_id"]
        with client.app.state.service.lock:
            assert client.post(f"/workbooks/{wid}/process").status_code == 409


def test_empty_workbook(settings):
    from io import BytesIO

    from openpyxl import Workbook

    stream = BytesIO()
    Workbook().save(stream)
    with TestClient(create_app(settings)) as client:
        wid = client.post("/workbooks/upload", files={"file": ("empty.xlsx", stream.getvalue())}).json()[
            "workbook_id"
        ]
        run = client.post(f"/workbooks/{wid}/process").json()
        assert run["stage"] == "COMPLETED"
        assert client.get(f"/workbooks/{wid}/tables").json() == []
        assert client.get(f"/workbooks/{wid}/formulas").json() == []
