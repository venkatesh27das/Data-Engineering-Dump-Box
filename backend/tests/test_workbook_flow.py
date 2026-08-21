import io
import time

from openpyxl import Workbook


def workbook_bytes() -> bytes:
    output = io.BytesIO()
    book = Workbook()
    sheet = book.active
    sheet.title = "Orders"
    sheet.append(["Order ID", "Amount"])
    sheet.append(["ORD-1", 1200])
    sheet.append(["ORD-2", 900])
    book.save(output)
    return output.getvalue()


def wait_for_run(client, run_id: str) -> dict:
    for _ in range(100):
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] in {"completed", "needs_review", "failed"}:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_upload_to_package(client):
    response = client.post(
        "/api/v1/workbooks",
        files={
            "file": (
                "orders.xlsx",
                workbook_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"purpose": "Knowledge extraction", "description": "Orders test"},
    )
    assert response.status_code == 200
    payload = response.json()
    run = wait_for_run(client, payload["run"]["id"])
    assert run["status"] == "completed"
    assert run["output_unit_count"] > 0
    assets = client.get(f"/api/v1/runs/{run['id']}/assets").json()
    table_asset = next(asset for asset in assets if asset["asset_type"] == "table")
    assert any(asset["asset_type"] == "semantic_unit" for asset in assets)
    assert any(asset["asset_type"] == "relationship" for asset in assets)
    content = client.get(f"/api/v1/assets/{table_asset['id']}/content")
    assert content.status_code == 200
    assert content.json()["content_kind"] == "table"
    assert len(content.json()["preview_rows"]) == 2
    asset_download = client.get(f"/api/v1/assets/{table_asset['id']}/download")
    assert asset_download.status_code == 200
    assert asset_download.content.startswith(b"PAR1")
    trace = client.get(f"/api/v1/runs/{run['id']}/trace")
    assert trace.status_code == 200
    assert any(stage["stage"] == "extracting" for stage in trace.json()["stages"])
    assert trace.json()["lineage"]["technical_count"] > 0
    package = client.get(f"/api/v1/runs/{run['id']}/package/download")
    assert package.status_code == 200
    assert package.content.startswith(b"PK")


def test_feedback_creates_child_run(client):
    upload = client.post(
        "/api/v1/workbooks",
        files={"file": ("orders.xlsx", workbook_bytes())},
        data={"purpose": "Knowledge extraction"},
    ).json()
    wait_for_run(client, upload["run"]["id"])
    response = client.post(
        f"/api/v1/runs/{upload['run']['id']}/reprocess",
        json={
            "raw_text": "Treat row 1 on Orders as the header.",
            "scope": "impacted_assets",
            "preserve_approved_assets": True,
        },
    )
    assert response.status_code == 200
    child = response.json()
    assert child["parent_run_id"] == upload["run"]["id"]
    assert child["trigger_type"] == "feedback_rerun"
    completed = wait_for_run(client, child["id"])
    assert completed["status"] == "completed"
