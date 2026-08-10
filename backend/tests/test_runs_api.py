from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services.task_manager import task_manager
from app.storage.database import Database, get_database


@pytest.fixture
def run_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runs.db'}", upload_dir=str(tmp_path / "uploads"), artifact_dir=str(tmp_path / "artifacts"))
    database = Database(settings.sqlite_path)

    def discard(coroutine):
        coroutine.close()

    monkeypatch.setattr(task_manager, "start", discard)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_start_retrieve_and_list_run_events(run_client: TestClient) -> None:
    project = run_client.post("/api/v1/projects", json={"name": "Run Graph", "knowledge_objective": "Find supplier contracts"}).json()
    uploaded = run_client.post(f"/api/v1/projects/{project['id']}/sources", files={"file": ("schema.sql", b"CREATE TABLE supplier(id INT);", "text/plain")})
    assert uploaded.status_code == 201
    started = run_client.post(f"/api/v1/projects/{project['id']}/runs")
    assert started.status_code == 202
    run = started.json()
    assert run["status"] == "queued"
    assert run_client.get(f"/api/v1/projects/{project['id']}/runs/{run['id']}").status_code == 200
    events = run_client.get(f"/api/v1/projects/{project['id']}/runs/{run['id']}/events").json()
    assert events[0]["title"] == "Run queued"
