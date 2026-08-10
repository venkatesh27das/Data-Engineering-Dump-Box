from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.storage.database import Database, get_database


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=1,
    )
    database = Database(settings.sqlite_path)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_project(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Supplier Knowledge Graph",
            "knowledge_objective": "Understand suppliers and their contracts.",
            "processing_mode": "hybrid",
            "graph_depth": "entity_relationships",
            "review_low_confidence": True,
            "max_tokens": 4096,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_retrieve_and_update_project(client: TestClient) -> None:
    project = _create_project(client)

    retrieved = client.get(f"/api/v1/projects/{project['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["processing_mode"] == "hybrid"

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"graph_depth": "semantic", "max_tokens": 8192},
    )
    assert updated.status_code == 200
    assert updated.json()["graph_depth"] == "semantic"
    assert updated.json()["max_tokens"] == 8192


def test_upload_list_and_delete_source(client: TestClient, tmp_path: Path) -> None:
    project = _create_project(client)
    project_id = project["id"]

    uploaded = client.post(
        f"/api/v1/projects/{project_id}/sources",
        files={"file": ("supplier_schema.sql", b"CREATE TABLE supplier (id INT);", "text/plain")},
    )
    assert uploaded.status_code == 201
    source = uploaded.json()
    assert source["category"] == "structured"
    assert Path(source["storage_path"]).is_file()

    listed = client.get(f"/api/v1/projects/{project_id}/sources")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [source["id"]]

    deleted = client.delete(f"/api/v1/projects/{project_id}/sources/{source['id']}")
    assert deleted.status_code == 204
    assert not Path(source["storage_path"]).exists()


def test_rejects_unsupported_upload(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/sources",
        files={"file": ("malware.exe", b"not executable", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
