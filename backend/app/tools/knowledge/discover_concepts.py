from app.domain.assets import Concept
from app.domain.extraction import ConceptDiscoveryResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, validate_evidence


async def discover_concepts(provider: ModelProvider, sources: list[NormalizedSource], objective: str) -> list[Concept]:
    response = await provider.structured_generate(
        extraction_messages(task="Discover business concepts, definitions, synonyms, and optional broader-concept links.", objective=objective, sources=sources),
        ConceptDiscoveryResponse,
    )
    validate_evidence(((concept.id, concept.evidence) for concept in response.concepts), sources)
    return response.concepts
