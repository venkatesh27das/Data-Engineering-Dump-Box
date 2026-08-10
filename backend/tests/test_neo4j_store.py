from datetime import UTC, datetime

import pytest
from neo4j.time import DateTime as Neo4jDateTime

from app.domain.assets import (
    Entity,
    GraphSchema,
    KnowledgeAssetPackage,
    QualityDisposition,
    QualityReport,
    Relationship,
    ReviewStatus,
)
from app.graph.neo4j_store import Neo4jGraphStore


class FakeResult:
    async def consume(self) -> None:
        return None


class FakeTransaction:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[dict[str, object]]]] = []

    async def run(self, query: str, *, rows: list[dict[str, object]]) -> FakeResult:
        self.calls.append((query, rows))
        return FakeResult()


class FakeSession:
    def __init__(self, transaction: FakeTransaction) -> None:
        self.transaction = transaction

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def execute_write(self, callback, *args):
        return await callback(self.transaction, *args)


class FakeDriver:
    def __init__(self) -> None:
        self.transaction = FakeTransaction()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    def session(self, *, database: str) -> FakeSession:
        assert database == "neo4j"
        return FakeSession(self.transaction)


def package() -> KnowledgeAssetPackage:
    approved = ReviewStatus.APPROVED
    return KnowledgeAssetPackage(
        package_id="PKG-1",
        project_id="PROJECT-1",
        sources=[],
        entities=[
            Entity(id="ENT-1", canonical_name="ACME", entity_type="Supplier", confidence=.96, review_status=approved),
            Entity(id="ENT-2", canonical_name="Widget", entity_type="Product", confidence=.93, review_status=approved),
            Entity(id="ENT-3", canonical_name="Pending", entity_type="Supplier", confidence=.7),
        ],
        relationships=[
            Relationship(id="REL-1", source_entity_id="ENT-1", target_entity_id="ENT-2", relationship_type="SUPPLIES", confidence=.9, review_status=approved),
            Relationship(id="REL-2", source_entity_id="ENT-1", target_entity_id="ENT-3", relationship_type="SUPPLIES", confidence=.9, review_status=approved),
            Relationship(id="REL-3", source_entity_id="ENT-1", target_entity_id="ENT-2", relationship_type="unsafe type", confidence=.9, review_status=approved),
        ],
        graph_schema=GraphSchema(),
        quality_report=QualityReport(overall_score=.9, evidence_coverage=1, average_confidence=.9, consistency=1, completeness=.9, disposition=QualityDisposition.PASS),
        created_at=datetime.now(UTC),
    )


@pytest.mark.anyio
async def test_publication_is_approved_only_safe_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    store = Neo4jGraphStore(uri="neo4j+s://example", username="neo4j", password="secret")
    first_driver = FakeDriver()
    monkeypatch.setattr(store, "_driver", lambda: first_driver)
    first = await store.publish_package(package())
    assert first.nodes_published == 2
    assert first.relationships_published == 1
    assert first.assets_skipped == 3
    assert all("MERGE" in query for query, _ in first_driver.transaction.calls)
    assert all("unsafe type" not in query for query, _ in first_driver.transaction.calls)

    first_rows = [rows for _, rows in first_driver.transaction.calls]
    second_driver = FakeDriver()
    monkeypatch.setattr(store, "_driver", lambda: second_driver)
    second = await store.publish_package(package())
    assert second == first
    assert [rows for _, rows in second_driver.transaction.calls] == first_rows


def test_neo4j_temporal_values_are_json_safe() -> None:
    value = Neo4jDateTime(2026, 8, 10, 15, 30, 0)
    serialized = Neo4jGraphStore._serialize_neo4j({"updated_at": value})
    assert serialized == {"updated_at": "2026-08-10T15:30:00.000000000"}
