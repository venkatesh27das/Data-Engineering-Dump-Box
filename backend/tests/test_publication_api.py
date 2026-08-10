from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.assets import Entity, GraphSchema, KnowledgeAssetPackage, QualityDisposition, QualityReport, ReviewStatus
from app.domain.projects import ProjectCreate
from app.domain.publication import PublicationResult
from app.graph.base import GraphStore
from app.graph.dependencies import get_graph_store
from app.main import app
from app.repositories.projects import ProjectRepository
from app.repositories.runs import AssetPackageRepository, RunRepository
from app.storage.database import Database, get_database


class FakeGraphStore(GraphStore):
    def __init__(self, configured: bool = True) -> None:
        self._configured = configured
        self.packages: list[KnowledgeAssetPackage] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def health_check(self) -> bool:
        return self.configured

    async def publish_package(self, package: KnowledgeAssetPackage) -> PublicationResult:
        self.packages.append(package)
        approved = sum(entity.review_status == ReviewStatus.APPROVED for entity in package.entities)
        return PublicationResult(nodes_published=approved, relationships_published=0, assets_skipped=len(package.entities) - approved)

    async def get_subgraph(self, project_id: str):
        return {"nodes": [], "edges": []}

    async def get_node(self, project_id: str, node_id: str):
        return None

    async def query(self, project_id: str, cypher: str, parameters=None):
        return []


@pytest.fixture
def publication_client(tmp_path: Path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'publish.db'}", artifact_dir=str(tmp_path / "artifacts"))
    database = Database(settings.sqlite_path)
    project = ProjectRepository(database).create(ProjectCreate(name="Publish Graph", knowledge_objective="Publish approved suppliers"))
    run = RunRepository(database).create(project.id)
    package = KnowledgeAssetPackage(
        package_id="PKG-PUBLISH",
        project_id=project.id,
        sources=[],
        entities=[
            Entity(id="ENT-1", canonical_name="Approved", entity_type="Supplier", confidence=.95, review_status=ReviewStatus.APPROVED),
            Entity(id="ENT-2", canonical_name="Pending", entity_type="Supplier", confidence=.8),
        ],
        graph_schema=GraphSchema(),
        quality_report=QualityReport(overall_score=.9, evidence_coverage=1, average_confidence=.9, consistency=1, completeness=.9, disposition=QualityDisposition.PASS),
        created_at=datetime.now(UTC),
    )
    AssetPackageRepository(database, settings.artifact_path).save(package, run.id)
    graph_store = FakeGraphStore()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    with TestClient(app) as client:
        yield client, project.id, graph_store
    app.dependency_overrides.clear()


def test_publish_and_republish_create_history_without_changing_package(publication_client) -> None:
    client, project_id, graph_store = publication_client
    first = client.post(f"/api/v1/projects/{project_id}/publish/neo4j")
    second = client.post(f"/api/v1/projects/{project_id}/publish/neo4j")
    assert first.status_code == second.status_code == 201
    assert first.json()["nodes_published"] == second.json()["nodes_published"] == 1
    assert len(graph_store.packages) == 2

    status = client.get(f"/api/v1/projects/{project_id}/publish/status")
    assert status.status_code == 200
    assert status.json()["connected"] is True
    assert len(status.json()["history"]) == 2
