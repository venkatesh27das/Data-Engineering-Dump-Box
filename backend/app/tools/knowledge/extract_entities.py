from app.domain.assets import Entity
from app.domain.extraction import EntityExtractionResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, generate_required_collection, validate_evidence


async def extract_entities(
    provider: ModelProvider,
    sources: list[NormalizedSource],
    objective: str,
    *,
    max_tokens: int | None = None,
) -> list[Entity]:
    response = await generate_required_collection(
        provider,
        extraction_messages(
            task=(
                "Extract canonical business entities, aliases, attributes, confidence, and precise provenance. "
                "Treat named organizations, people, agreements or contracts, products, services, and stable "
                "business identifiers as entity candidates when supported."
            ),
            objective=objective,
            sources=sources,
        ),
        EntityExtractionResponse,
        collection_field="entities",
        asset_description="named organizations, agreements, products, services, and identifiers as entities",
        sources=sources,
        max_tokens=max_tokens,
    )
    validate_evidence(((entity.id, entity.evidence) for entity in response.entities), sources)
    return response.entities
