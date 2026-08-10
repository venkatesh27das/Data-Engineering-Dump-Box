from datetime import UTC, datetime
from uuid import uuid4

from app.domain.assets import KnowledgeAssetPackage, Relationship
from app.domain.normalized import NormalizedSource
from app.domain.projects import SourceAsset
from app.providers.base import ModelProvider
from app.tools.graph import build_graph_schema
from app.tools.knowledge import (
    discover_concepts,
    extract_entities,
    extract_events,
    extract_facts,
    extract_relationships,
    map_semantics,
    resolve_entities,
)
from app.tools.quality import score_assets


class KnowledgePackageBuilder:
    """Milestone 5 verification harness for independently callable tools.

    The Milestone 6 supervisor will replace this fixed invocation order at runtime.
    """

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    async def build(
        self,
        *,
        project_id: str,
        sources: list[SourceAsset],
        normalized_sources: list[NormalizedSource],
        objective: str,
    ) -> KnowledgeAssetPackage:
        source_ids = {source.id for source in sources}
        normalized_ids = {source.source_id for source in normalized_sources}
        if source_ids != normalized_ids:
            raise ValueError("Uploaded and normalized source IDs do not match")

        concepts = await discover_concepts(self.provider, normalized_sources, objective)
        candidate_entities = await extract_entities(self.provider, normalized_sources, objective)
        resolution = resolve_entities(candidate_entities)
        relationships = await extract_relationships(self.provider, normalized_sources, objective, resolution.entities)
        relationships = self._apply_redirects(relationships, resolution.redirects)
        facts = await extract_facts(self.provider, normalized_sources, objective)
        events = await extract_events(self.provider, normalized_sources, objective)
        semantic_mappings = await map_semantics(self.provider, normalized_sources, objective, concepts)
        graph_schema = build_graph_schema(resolution.entities, relationships)
        quality_report = score_assets(
            entities=resolution.entities,
            relationships=relationships,
            concepts=concepts,
            facts=facts,
            events=events,
            semantic_mappings=semantic_mappings,
            ambiguous_entities=len(resolution.ambiguous_matches),
        )
        return KnowledgeAssetPackage(
            package_id=str(uuid4()),
            project_id=project_id,
            sources=sources,
            entities=resolution.entities,
            relationships=relationships,
            concepts=concepts,
            facts=facts,
            events=events,
            semantic_mappings=semantic_mappings,
            graph_schema=graph_schema,
            quality_report=quality_report,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _apply_redirects(relationships: list[Relationship], redirects: dict[str, str]) -> list[Relationship]:
        updated: list[Relationship] = []
        seen: set[tuple[str, str, str]] = set()
        for relationship in relationships:
            source_id = redirects.get(relationship.source_entity_id, relationship.source_entity_id)
            target_id = redirects.get(relationship.target_entity_id, relationship.target_entity_id)
            if source_id == target_id:
                continue
            key = (source_id, target_id, relationship.relationship_type)
            if key in seen:
                continue
            seen.add(key)
            updated.append(relationship.model_copy(update={"source_entity_id": source_id, "target_entity_id": target_id}))
        return updated
