import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.repositories.runs import RunArtifactRepository, RunRepository
from app.services.task_manager import task_manager
from app.storage.database import Database, get_database


@pytest.fixture
def run_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runs.db'}", upload_dir=str(tmp_path / "uploads"), artifact_dir=str(tmp_path / "artifacts"))
    database = Database(settings.sqlite_path)

    active_runs: set[str] = set()

    def discard(run_id, _coroutine_factory):
        active_runs.add(run_id)

    async def cancel_and_wait(run_id):
        if run_id not in active_runs:
            return False
        active_runs.remove(run_id)
        return True

    monkeypatch.setattr(task_manager, "start", discard)
    monkeypatch.setattr(task_manager, "is_active", lambda run_id: run_id in active_runs)
    monkeypatch.setattr(task_manager, "cancel_and_wait", cancel_and_wait)
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


def test_queue_detail_cancel_and_delete_lifecycle(run_client: TestClient, tmp_path: Path) -> None:
    project = run_client.post(
        "/api/v1/projects",
        json={"name": "Background Graph", "knowledge_objective": "Track supplier obligations"},
    ).json()
    uploaded = run_client.post(
        f"/api/v1/projects/{project['id']}/sources",
        files={"file": ("contracts.sql", b"CREATE TABLE contracts(id INT);", "text/plain")},
    )
    assert uploaded.status_code == 201
    run = run_client.post(f"/api/v1/projects/{project['id']}/runs").json()

    database = Database(tmp_path / "runs.db")
    artifact = RunArtifactRepository(database).add(
        run["id"],
        stage="source_analysis",
        artifact_type="normalized_source",
        name="Normalized contracts.sql",
        parent_ids=[uploaded.json()["id"]],
        record_count=1,
    )
    package_dir = tmp_path / "artifacts" / project["id"]
    package_dir.mkdir(parents=True)
    package_path = package_dir / "package-1.json"
    package_path.write_text("{}", encoding="utf-8")
    checkpoint_path = tmp_path / "artifacts" / "langgraph-checkpoints.db"
    with sqlite3.connect(checkpoint_path) as checkpoint_connection:
        checkpoint_connection.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint_id TEXT)")
        checkpoint_connection.execute("INSERT INTO checkpoints VALUES (?, ?)", (run["id"], "target"))
        checkpoint_connection.execute("INSERT INTO checkpoints VALUES (?, ?)", ("another-run", "keep"))
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO asset_packages (
                package_id, project_id, run_id, artifact_path, entity_count,
                relationship_count, concept_count, fact_count, event_count,
                quality_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("package-1", project["id"], run["id"], str(package_path), 1, 0, 1, 0, 0, 0.9, datetime.now(UTC).isoformat()),
        )

    queue = run_client.get("/api/v1/runs")
    assert queue.status_code == 200
    assert queue.json()[0]["run"]["id"] == run["id"]
    assert queue.json()[0]["artifact_count"] == 1

    detail = run_client.get(f"/api/v1/runs/{run['id']}")
    assert detail.status_code == 200
    assert detail.json()["temporary_assets"][0]["id"] == artifact.id
    assert detail.json()["lineage"] == [{
        "parent_id": uploaded.json()["id"],
        "child_id": artifact.id,
        "relationship": "normalized_from",
    }]

    canceled = run_client.post(f"/api/v1/runs/{run['id']}/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["run"]["status"] == "canceled"
    canceled_detail = run_client.get(f"/api/v1/runs/{run['id']}").json()
    assert canceled_detail["events"][-1]["status"] == "canceled"

    deleted = run_client.delete(f"/api/v1/runs/{run['id']}")
    assert deleted.status_code == 204
    assert not package_path.exists()
    with sqlite3.connect(checkpoint_path) as checkpoint_connection:
        assert checkpoint_connection.execute("SELECT checkpoint_id FROM checkpoints").fetchall() == [("keep",)]
    assert run_client.get(f"/api/v1/runs/{run['id']}").status_code == 404


def test_active_process_must_be_canceled_before_delete(run_client: TestClient) -> None:
    project = run_client.post(
        "/api/v1/projects",
        json={"name": "Protected Graph", "knowledge_objective": "Protect active generation"},
    ).json()
    run_client.post(
        f"/api/v1/projects/{project['id']}/sources",
        files={"file": ("schema.sql", b"CREATE TABLE protected(id INT);", "text/plain")},
    )
    run = run_client.post(f"/api/v1/projects/{project['id']}/runs").json()

    response = run_client.delete(f"/api/v1/runs/{run['id']}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Cancel the process before deleting it"


def test_queue_marks_orphaned_process_as_interrupted(run_client: TestClient, tmp_path: Path) -> None:
    project = run_client.post(
        "/api/v1/projects",
        json={"name": "Interrupted Graph", "knowledge_objective": "Recover truthful queue state"},
    ).json()
    database = Database(tmp_path / "runs.db")
    orphaned = RunRepository(database).create(project["id"])

    response = run_client.get(f"/api/v1/runs/{orphaned.id}")

    assert response.status_code == 200
    assert response.json()["item"]["run"]["status"] == "failed"
    assert response.json()["item"]["run"]["current_stage"] == "interrupted"
    assert response.json()["events"][-1]["title"] == "Process interrupted"
