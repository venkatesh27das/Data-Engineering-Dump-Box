from app.domain.assets import Event
from app.domain.extraction import EventExtractionResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, validate_evidence


async def extract_events(provider: ModelProvider, sources: list[NormalizedSource], objective: str) -> list[Event]:
    response = await provider.structured_generate(
        extraction_messages(task="Extract explicit events and temporal assertions. Return no events when the sources do not support them.", objective=objective, sources=sources),
        EventExtractionResponse,
    )
    validate_evidence(((event.id, event.evidence) for event in response.events), sources)
    return response.events
