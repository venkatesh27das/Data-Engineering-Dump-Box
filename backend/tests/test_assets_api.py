from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.assets import (
    Entity,
    EvidenceReference,
    GraphSchema,
    KnowledgeAssetPackage,
    QualityDisposition,
    QualityReport,
)
from app.domain.projects import ProjectCreate
from app.main import app
from app.repositories.projects import ProjectRepository
from app.repositories.runs import AssetPackageRepository, RunRepository
from app.storage.database import Database, get_database


@pytest.fixture
def asset_client(tmp_path: Path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'assets.db'}", artifact_dir=str(tmp_path / "artifacts"))
    database = Database(settings.sqlite_path)
    project = ProjectRepository(database).create(ProjectCreate(name="Review Graph", knowledge_objective="Review suppliers"))
    run = RunRepository(database).create(project.id)
    evidence = EvidenceReference(source_id="SRC-1", source_name="suppliers.pdf", page=2, excerpt="ACME supplies widgets")
    package = KnowledgeAssetPackage(
        package_id="PKG-1",
        project_id=project.id,
        sources=[],
        entities=[
            Entity(id="ENT-1", canonical_name="ACME", entity_type="Supplier", confidence=0.96, evidence=[evidence]),
            Entity(id="ENT-2", canonical_name="Widget", entity_type="Product", confidence=0.72, evidence=[evidence]),
        ],
        graph_schema=GraphSchema(),
        quality_report=QualityReport(overall_score=0.88, evidence_coverage=1, average_confidence=0.84, consistency=1, completeness=0.8, disposition=QualityDisposition.REVIEW_REQUIRED),
        created_at=datetime.now(UTC),
    )
    AssetPackageRepository(database, settings.artifact_path).save(package, run.id)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as client:
        yield client, project.id, database, settings
    app.dependency_overrides.clear()


def test_generated_package_is_browsable_and_filterable(asset_client) -> None:
    client, project_id, _, _ = asset_client
    overview = client.get(f"/api/v1/projects/{project_id}/assets")
    assert overview.status_code == 200
    assert overview.json()["package"]["entity_count"] == 2

    page = client.get(f"/api/v1/projects/{project_id}/assets/entities", params={"minimum_confidence": 0.9, "source": "suppliers.pdf"})
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["evidence"][0]["excerpt"] == "ACME supplies widgets"


def test_review_state_persists_in_package_and_audit_log(asset_client) -> None:
    client, project_id, database, settings = asset_client
    response = client.post(f"/api/v1/projects/{project_id}/assets/ENT-1/approve", json={"note": "Verified against source"})
    assert response.status_code == 200
    assert response.json()["asset"]["review_status"] == "approved"

    package = AssetPackageRepository(database, settings.artifact_path).load_latest(project_id)
    assert package and package.entities[0].review_status.value == "approved"
    with database.connect() as connection:
        decision = connection.execute("SELECT decision, note FROM review_decisions WHERE asset_id = ?", ("ENT-1",)).fetchone()
    assert decision and decision["decision"] == "approved" and decision["note"] == "Verified against source"
