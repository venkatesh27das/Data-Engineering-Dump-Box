from app.domain.assets import Entity
from app.domain.extraction import EntityExtractionResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, validate_evidence


async def extract_entities(provider: ModelProvider, sources: list[NormalizedSource], objective: str) -> list[Entity]:
    response = await provider.structured_generate(
        extraction_messages(task="Extract canonical business entities, aliases, attributes, confidence, and precise provenance.", objective=objective, sources=sources),
        EntityExtractionResponse,
    )
    validate_evidence(((entity.id, entity.evidence) for entity in response.entities), sources)
    return response.entities
