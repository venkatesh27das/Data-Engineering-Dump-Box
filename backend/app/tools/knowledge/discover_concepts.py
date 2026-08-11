from app.domain.assets import Concept
from app.domain.extraction import ConceptDiscoveryResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, generate_required_collection, validate_evidence


async def discover_concepts(
    provider: ModelProvider,
    sources: list[NormalizedSource],
    objective: str,
    *,
    max_tokens: int | None = None,
) -> list[Concept]:
    response = await generate_required_collection(
        provider,
        extraction_messages(
            task=(
                "Discover business concepts, definitions, synonyms, and optional broader-concept links. "
                "Include concepts for parties, agreements, products, obligations, pricing, delivery, and payment "
                "terms when they are supported by the source."
            ),
            objective=objective,
            sources=sources,
        ),
        ConceptDiscoveryResponse,
        collection_field="concepts",
        asset_description="business concepts and definitions",
        sources=sources,
        max_tokens=max_tokens,
    )
    validate_evidence(((concept.id, concept.evidence) for concept in response.concepts), sources)
    return response.concepts
