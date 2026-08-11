import json
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
from app.domain.normalized import DocumentChunk, DocumentPage, NormalizedSource
from app.domain.projects import SourceAsset, SourceCategory
from app.providers.base import ChatMessage, ChatResponse, ModelProvider, StructuredModel
from app.services.knowledge_package_builder import KnowledgePackageBuilder
from app.tools.knowledge.common import KnowledgeToolError, source_context
from app.tools.knowledge.discover_concepts import discover_concepts
from app.tools.knowledge.extract_entities import extract_entities
from app.tools.knowledge.extract_relationships import extract_relationships
from app.tools.knowledge.resolve_entities import resolve_entities
from app.tools.documents.parse_pdf import parse_pdf
from app.tools.structured.parse_ddl import parse_ddl


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeKnowledgeProvider(ModelProvider):
    def __init__(self, *, missing_evidence: bool = False) -> None:
        self.missing_evidence = missing_evidence
        self.max_tokens_seen: list[int | None] = []

    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        self.max_tokens_seen.append(max_tokens)
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


class ContractRetryProvider(ModelProvider):
    def __init__(self) -> None:
        self.attempts: dict[str, int] = {}
        self.messages_seen: dict[str, list[list[ChatMessage]]] = {}

    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        name = response_model.__name__
        self.attempts[name] = self.attempts.get(name, 0) + 1
        self.messages_seen.setdefault(name, []).append(messages)
        if name in {ConceptDiscoveryResponse.__name__, EntityExtractionResponse.__name__} and self.attempts[name] == 1:
            return response_model.model_validate({})

        evidence = [{"source_id": "CONTRACT-1", "source_name": "contract_1032.pdf", "page": 1}]
        payloads: dict[str, dict[str, object]] = {
            ConceptDiscoveryResponse.__name__: {
                "concepts": [{"id": "CON-1", "name": "Supply Agreement", "definition": "An agreement governing supply obligations.", "confidence": 0.96, "evidence": evidence}]
            },
            EntityExtractionResponse.__name__: {
                "entities": [
                    {"id": "ENT-SUPPLIER", "canonical_name": "ACME Corporation", "entity_type": "Supplier", "aliases": ["ACME"], "confidence": 0.98, "evidence": evidence},
                    {"id": "ENT-BUYER", "canonical_name": "Northstar Manufacturing Group", "entity_type": "Buyer", "confidence": 0.97, "evidence": evidence},
                    {"id": "ENT-CONTRACT", "canonical_name": "CTR-1032", "entity_type": "Contract", "confidence": 0.99, "evidence": evidence},
                    {"id": "ENT-PRODUCT-X", "canonical_name": "Product X", "entity_type": "Product", "confidence": 0.97, "evidence": evidence},
                    {"id": "ENT-PRODUCT-Z", "canonical_name": "Product Z", "entity_type": "Product", "confidence": 0.97, "evidence": [{**evidence[0], "page": 2}]},
                ]
            },
            RelationshipExtractionResponse.__name__: {
                "relationships": [
                    {"id": "REL-1", "source_entity_id": "ENT-SUPPLIER", "target_entity_id": "ENT-CONTRACT", "relationship_type": "PARTY_TO", "confidence": 0.96, "evidence": evidence},
                    {"id": "REL-2", "source_entity_id": "ENT-CONTRACT", "target_entity_id": "ENT-PRODUCT-X", "relationship_type": "COVERS", "confidence": 0.95, "evidence": evidence},
                ]
            },
        }
        return response_model.model_validate(payloads[name])

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        return [[0.0] for _ in texts]

    async def health_check(self) -> bool:
        return True


class AlwaysEmptyProvider(ModelProvider):
    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        return response_model.model_validate({})

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
    provider = FakeKnowledgeProvider()
    package = await KnowledgePackageBuilder(provider).build(
        project_id="project-1",
        sources=[_source()],
        normalized_sources=[_normalized_source()],
        objective="Understand suppliers and contracts",
        max_tokens=2048,
    )
    assert len(package.entities) == 2
    assert len(package.relationships) == 1
    assert package.relationships[0].evidence[0].column == "supplier_id"
    assert package.quality_report.evidence_coverage == 1
    assert package.graph_schema.node_definitions
    assert all(asset.evidence for asset in [*package.entities, *package.relationships, *package.concepts, *package.facts, *package.semantic_mappings])
    assert provider.max_tokens_seen == [2048] * 6


@pytest.mark.anyio
async def test_extraction_rejects_assets_without_provenance() -> None:
    with pytest.raises(KnowledgeToolError, match="missing provenance"):
        await extract_entities(FakeKnowledgeProvider(missing_evidence=True), [_normalized_source()], "Understand suppliers")


@pytest.mark.anyio
async def test_contract_fixture_recovers_from_empty_model_response() -> None:
    contract_path = Path(__file__).parents[2] / "test" / "knowledge_graph_test_pack" / "contract_1032.pdf"
    source = parse_pdf(contract_path, source_id="CONTRACT-1", source_name="contract_1032.pdf")
    provider = ContractRetryProvider()
    objective = "Understand suppliers, contracts, products and contractual obligations."

    concepts = await discover_concepts(provider, [source], objective, max_tokens=2048)
    entities = await extract_entities(provider, [source], objective, max_tokens=2048)
    relationships = await extract_relationships(provider, [source], objective, entities, max_tokens=2048)

    assert concepts
    assert {entity.canonical_name for entity in entities} >= {
        "ACME Corporation",
        "Northstar Manufacturing Group",
        "CTR-1032",
        "Product X",
        "Product Z",
    }
    assert relationships
    assert provider.attempts[ConceptDiscoveryResponse.__name__] == 2
    assert provider.attempts[EntityExtractionResponse.__name__] == 2
    assert "previous response returned no entities" in provider.messages_seen[EntityExtractionResponse.__name__][1][-1].content


@pytest.mark.anyio
async def test_meaningful_source_rejects_repeated_empty_entity_response() -> None:
    with pytest.raises(KnowledgeToolError, match="no entities.*after one extraction retry"):
        await extract_entities(AlwaysEmptyProvider(), [_normalized_source()], "Understand suppliers", max_tokens=2048)


def test_entity_resolution_uses_aliases_before_similarity() -> None:
    entities = EntityExtractionResponse.model_validate({"entities": [
        {"id": "ENT-1", "canonical_name": "ACME Corporation", "entity_type": "Supplier", "aliases": ["ACME"], "confidence": 0.95},
        {"id": "ENT-2", "canonical_name": "ACME", "entity_type": "Supplier", "confidence": 0.9},
    ]}).entities
    result = resolve_entities(entities)
    assert len(result.entities) == 1
    assert result.redirects == {"ENT-2": "ENT-1"}
    assert result.merges[0].method == "exact_or_alias"


def test_source_context_uses_one_compact_document_representation() -> None:
    repeated_text = "purchase order supplier contract " * 2000
    source = NormalizedSource(
        source_id="SRC-1",
        source_name="purchase_order.png",
        modality="unstructured",
        source_type="image",
        text=repeated_text,
        pages=[DocumentPage(page_number=1, text=repeated_text, character_count=len(repeated_text))],
        chunks=[
            DocumentChunk(
                id="SRC-1-chunk-1",
                text=repeated_text,
                page=1,
                start_offset=0,
                end_offset=len(repeated_text),
            )
        ],
        parsing_confidence=0.8,
    )

    context = source_context([source])
    payload = json.loads(context)[0]
    assert len(context) <= 24_000
    assert "chunks" in payload
    assert "text" not in payload
    assert "pages" not in payload
    assert payload["truncated"] is True


def test_source_context_uses_tables_without_duplicate_structured_text() -> None:
    payload = json.loads(source_context([_normalized_source()]))[0]
    assert payload["tables"]
    assert "text" not in payload
    assert "chunks" not in payload
    assert "pages" not in payload
