import json

from app.domain.assets import Entity, Relationship
from app.domain.extraction import RelationshipExtractionResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import KnowledgeToolError, extraction_messages, validate_evidence


async def extract_relationships(provider: ModelProvider, sources: list[NormalizedSource], objective: str, entities: list[Entity]) -> list[Relationship]:
    entity_context = json.dumps([entity.model_dump(mode="json") for entity in entities], ensure_ascii=False)
    response = await provider.structured_generate(
        extraction_messages(task="Extract evidence-linked relationships using only the supplied entity IDs.", objective=objective, sources=sources, extra_context=entity_context),
        RelationshipExtractionResponse,
    )
    entity_ids = {entity.id for entity in entities}
    invalid = [relationship.id for relationship in response.relationships if relationship.source_entity_id not in entity_ids or relationship.target_entity_id not in entity_ids]
    if invalid:
        raise KnowledgeToolError(f"Relationships reference unknown entities: {', '.join(invalid)}")
    validate_evidence(((relationship.id, relationship.evidence) for relationship in response.relationships), sources)
    return response.relationships
