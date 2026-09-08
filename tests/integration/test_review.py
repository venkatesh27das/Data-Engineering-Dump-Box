import hashlib
import json
from io import BytesIO
from pathlib import Path

import openpyxl
from fastapi.testclient import TestClient

from app.api.main import create_app


def test_feedback_region_child_run(settings):
    wb = openpyxl.Workbook()
    wb.active.append([1, 2])
    wb.active.append([3, 4])
    stream = BytesIO()
    wb.save(stream)
    with TestClient(create_app(settings)) as client:
        wid = client.post("/workbooks/upload", files={"file": ("review.xlsx", stream.getvalue())}).json()[
            "workbook_id"
        ]
        parent = client.post(f"/workbooks/{wid}/process").json()
        source = settings.output_dir / parent["run_id"]
        before = {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()
        }
        regions = client.get(f"/workbooks/{wid}/regions").json()
        region = next(r for r in regions if r["region_type"] == "unknown")
        rid = region["region_id"]
        assert (
            client.post(
                f"/regions/{rid}/feedback", json={"content": "Numeric table without headers"}
            ).status_code
            == 201
        )
        response = client.post(f"/regions/{rid}/reprocess", json={"expected_region_type": "kpi_block"})
        child = response.json()
        assert child["stage"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS"), child
        assert child["parent_run_id"] == parent["run_id"]
        assert before == {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file()
        }
        tables = client.get(f"/workbooks/{wid}/tables").json()
        assert tables[0]["row_count"] == 2
        assert tables[0]["source_rows"] == [1, 2]
        assert tables[0]["parquet_path"] == f"tables/{tables[0]['table_id']}.parquet"
        assert client.get(f"/regions/{rid}").json()["run_id"] == parent["run_id"]
        manifest = json.loads((settings.output_dir / child["run_id"] / "manifest.json").read_text())
        assert manifest["counts"]["tables"] == 1
        assert (
            client.post(f"/regions/{rid}/feedback", json={"expected_region_type": "invalid"}).status_code
            == 422
        )


def test_child_run_renames_copied_asset_files(settings, samples):
    with TestClient(create_app(settings)) as client:
        workbook_id = client.post(
            "/workbooks/upload",
            files={"file": ("complex.xlsx", samples["fixture_complex"].read_bytes())},
        ).json()["workbook_id"]
        parent = client.post(f"/workbooks/{workbook_id}/process").json()
        region = next(
            item
            for item in client.get(f"/workbooks/{workbook_id}/regions").json()
            if item["region_type"] == "unknown"
        )
        child = client.post(
            f"/regions/{region['region_id']}/reprocess",
            json={"expected_region_type": "narrative"},
        ).json()
        assert child["stage"] != "FAILED", child
        output = settings.output_dir / child["run_id"]
        for table in client.get(f"/workbooks/{workbook_id}/tables").json():
            assert table["parquet_path"] == f"tables/{table['table_id']}.parquet"
            assert (output / table["parquet_path"]).exists()
        for image in client.get(f"/workbooks/{workbook_id}/images").json():
            assert Path(image["filename"]).stem == image["image_id"]
            assert (output / image["filename"]).exists()
        assert not list((output / "renders").iterdir())
        assert (settings.output_dir / parent["run_id"] / "manifest.json").exists()
