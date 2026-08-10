from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.domain.assets import KnowledgeAssetPackage
from app.domain.projects import ProjectCreate
from app.domain.publication import PublicationResult
from app.graph.base import GraphStore
from app.graph.dependencies import get_graph_store
from app.main import app
from app.repositories.projects import ProjectRepository
from app.services.cypher_guard import validate_read_only_cypher
from app.storage.database import Database, get_database


class ExplorerGraphStore(GraphStore):
    configured = True

    def __init__(self) -> None:
        self.last_query: tuple[str, dict[str, object]] | None = None

    async def health_check(self) -> bool:
        return True

    async def publish_package(self, package: KnowledgeAssetPackage) -> PublicationResult:
        raise NotImplementedError

    async def get_subgraph(self, project_id: str):
        return {
            "nodes": [
                {"data": {"id": "ENT-1", "label": "ACME", "type": "Supplier", "confidence": .96, "sources": ["supplier.sql"], "search_text": "acme supplier"}},
                {"data": {"id": "ENT-2", "label": "Widget", "type": "Product", "confidence": .92, "sources": ["catalog.pdf"], "search_text": "widget product"}},
            ],
            "edges": [{"data": {"id": "REL-1", "source": "ENT-1", "target": "ENT-2", "label": "SUPPLIES", "confidence": .9, "search_text": "supplies"}}],
        }

    async def get_node(self, project_id: str, node_id: str):
        if node_id != "ENT-1":
            return None
        return {"id": "ENT-1", "name": "ACME", "type": "Supplier", "labels": ["Entity", "Supplier"], "confidence": .96, "description": "A supplier", "sources": ["supplier.sql"], "properties": {"supplier_id": "SUP-1"}, "evidence": [{"source_name": "supplier.sql", "table": "suppliers"}], "relationships": [{"id": "REL-1", "type": "SUPPLIES", "direction": "outgoing", "other_node_id": "ENT-2", "other_node_label": "Widget", "confidence": .9}]}

    async def query(self, project_id: str, cypher: str, parameters=None):
        self.last_query = (cypher, parameters or {})
        return [{"name": "ACME"}]


@pytest.fixture
def graph_client(tmp_path: Path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'graph.db'}")
    database = Database(settings.sqlite_path)
    project = ProjectRepository(database).create(ProjectCreate(name="Explorer", knowledge_objective="Explore suppliers"))
    store = ExplorerGraphStore()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_graph_store] = lambda: store
    with TestClient(app) as client:
        yield client, project.id, store
    app.dependency_overrides.clear()


def test_graph_and_node_endpoints_return_cytoscape_and_provenance(graph_client) -> None:
    client, project_id, _ = graph_client
    graph = client.get(f"/api/v1/projects/{project_id}/graph")
    assert graph.status_code == 200
    assert graph.json()["counts"] == {"nodes": 2, "relationships": 1, "node_types": 2, "relationship_types": 1}
    node = client.get(f"/api/v1/projects/{project_id}/graph/node/ENT-1")
    assert node.status_code == 200
    assert node.json()["evidence"][0]["table"] == "suppliers"
    assert node.json()["relationships"][0]["other_node_label"] == "Widget"


def test_query_endpoint_enforces_read_only_project_scoped_cypher(graph_client) -> None:
    client, project_id, store = graph_client
    unsafe = client.post(f"/api/v1/projects/{project_id}/graph/query", json={"query": "MATCH (n) DELETE n RETURN n"})
    assert unsafe.status_code == 400
    safe = client.post(f"/api/v1/projects/{project_id}/graph/query", json={"query": "MATCH (n:KnowledgeAsset) WHERE n.project_id = $project_id RETURN n.name AS name"})
    assert safe.status_code == 200 and safe.json()["row_count"] == 1
    assert store.last_query and store.last_query[0].endswith("LIMIT 100")
    assert store.last_query[1]["project_id"] == project_id


@pytest.mark.parametrize("query", [
    "MATCH (n) WHERE n.project_id = $project_id SET n.name = 'x' RETURN n",
    "CALL db.labels() YIELD label RETURN label",
    "MATCH (n) RETURN n",
    "MATCH (n) WHERE n.project_id = $project_id RETURN n LIMIT 201",
])
def test_cypher_guard_rejects_unsafe_queries(query: str) -> None:
    with pytest.raises(ValueError):
        validate_read_only_cypher(query)
