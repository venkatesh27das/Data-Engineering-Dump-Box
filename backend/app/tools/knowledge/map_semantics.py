import json

from app.domain.assets import Concept, SemanticMapping
from app.domain.extraction import SemanticMappingResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import KnowledgeToolError, extraction_messages, validate_evidence


async def map_semantics(
    provider: ModelProvider,
    sources: list[NormalizedSource],
    objective: str,
    concepts: list[Concept],
    *,
    max_tokens: int | None = None,
) -> list[SemanticMapping]:
    context = json.dumps([concept.model_dump(mode="json") for concept in concepts], ensure_ascii=False)
    response = await provider.structured_generate(
        extraction_messages(task="Map source schema/document terms to the supplied semantic concept IDs.", objective=objective, sources=sources, extra_context=context),
        SemanticMappingResponse,
        max_tokens=max_tokens,
    )
    concept_ids = {concept.id for concept in concepts}
    invalid = [mapping.id for mapping in response.semantic_mappings if mapping.target_concept_id not in concept_ids]
    if invalid:
        raise KnowledgeToolError(f"Semantic mappings reference unknown concepts: {', '.join(invalid)}")
    validate_evidence(((mapping.id, mapping.evidence) for mapping in response.semantic_mappings), sources)
    return response.semantic_mappings
