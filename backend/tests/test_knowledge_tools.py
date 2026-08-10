from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.extraction import (
    ConceptDiscoveryResponse,
    EntityExtractionResponse,
    EventExtractionResponse,
    FactExtractionResponse,
    RelationshipExtractionResponse,
    SemanticMappingResponse,
)
from app.domain.projects import SourceAsset, SourceCategory
from app.providers.base import ChatMessage, ChatResponse, ModelProvider, StructuredModel
from app.services.knowledge_package_builder import KnowledgePackageBuilder
from app.tools.knowledge.common import KnowledgeToolError
from app.tools.knowledge.extract_entities import extract_entities
from app.tools.knowledge.resolve_entities import resolve_entities
from app.tools.structured.parse_ddl import parse_ddl


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeKnowledgeProvider(ModelProvider):
    def __init__(self, *, missing_evidence: bool = False) -> None:
        self.missing_evidence = missing_evidence

    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        evidence = [] if self.missing_evidence else [{"source_id": "SRC-1", "source_name": "supplier_schema.sql", "table": "suppliers"}]
        responses: dict[str, dict[str, object]] = {
            EntityExtractionResponse.__name__: {"entities": [
                {"id": "ENT-1", "canonical_name": "ACME Corporation", "entity_type": "Supplier", "aliases": ["ACME"], "confidence": 0.97, "evidence": evidence},
                {"id": "ENT-2", "canonical_name": "Contract 1032", "entity_type": "Contract", "confidence": 0.94, "evidence": [{"source_id": "SRC-1", "source_name": "supplier_schema.sql", "table": "contracts"}]},
            ]},
            RelationshipExtractionResponse.__name__: {"relationships": [{"id": "REL-1", "source_entity_id": "ENT-1", "target_entity_id": "ENT-2", "relationship_type": "HAS_CONTRACT", "confidence": 0.93, "evidence": [{"source_id": "SRC-1", "source_name": "supplier_schema.sql", "table": "contracts", "column": "supplier_id"}]}]},
            ConceptDiscoveryResponse.__name__: {"concepts": [{"id": "CON-1", "name": "Supplier", "definition": "An organization providing goods or services.", "confidence": 0.95, "evidence": evidence}]},
            FactExtractionResponse.__name__: {"facts": [{"id": "FACT-1", "subject": "ACME Corporation", "predicate": "has contract", "object": "Contract 1032", "confidence": 0.92, "evidence": evidence}]},
            EventExtractionResponse.__name__: {"events": []},
            SemanticMappingResponse.__name__: {"semantic_mappings": [{"id": "MAP-1", "source_term": "suppliers", "target_concept_id": "CON-1", "mapping_type": "exact", "confidence": 0.96, "evidence": evidence}]},
        }
        return response_model.model_validate(responses[response_model.__name__])

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        return [[0.0] for _ in texts]

    async def health_check(self) -> bool:
        return True


def _source() -> SourceAsset:
    return SourceAsset(id="SRC-1", project_id="project-1", filename="supplier_schema.sql", original_filename="supplier_schema.sql", category=SourceCategory.STRUCTURED, extension=".sql", mime_type="text/plain", size_bytes=200, storage_path=str(Path("supplier_schema.sql")), created_at=datetime.now(UTC))


def _normalized_source():
    return parse_ddl("CREATE TABLE suppliers (supplier_id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE contracts (contract_id INTEGER PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(supplier_id));", source_id="SRC-1", source_name="supplier_schema.sql")


@pytest.mark.anyio
async def test_small_source_set_produces_valid_package() -> None:
    package = await KnowledgePackageBuilder(FakeKnowledgeProvider()).build(project_id="project-1", sources=[_source()], normalized_sources=[_normalized_source()], objective="Understand suppliers and contracts")
    assert len(package.entities) == 2
    assert len(package.relationships) == 1
    assert package.relationships[0].evidence[0].column == "supplier_id"
    assert package.quality_report.evidence_coverage == 1
    assert package.graph_schema.node_definitions
    assert all(asset.evidence for asset in [*package.entities, *package.relationships, *package.concepts, *package.facts, *package.semantic_mappings])


@pytest.mark.anyio
async def test_extraction_rejects_assets_without_provenance() -> None:
    with pytest.raises(KnowledgeToolError, match="missing provenance"):
        await extract_entities(FakeKnowledgeProvider(missing_evidence=True), [_normalized_source()], "Understand suppliers")


def test_entity_resolution_uses_aliases_before_similarity() -> None:
    entities = EntityExtractionResponse.model_validate({"entities": [
        {"id": "ENT-1", "canonical_name": "ACME Corporation", "entity_type": "Supplier", "aliases": ["ACME"], "confidence": 0.95},
        {"id": "ENT-2", "canonical_name": "ACME", "entity_type": "Supplier", "confidence": 0.9},
    ]}).entities
    result = resolve_entities(entities)
    assert len(result.entities) == 1
    assert result.redirects == {"ENT-2": "ENT-1"}
    assert result.merges[0].method == "exact_or_alias"
