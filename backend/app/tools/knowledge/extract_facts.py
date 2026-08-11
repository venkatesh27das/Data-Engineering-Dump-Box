from app.domain.assets import Fact
from app.domain.extraction import FactExtractionResponse
from app.domain.normalized import NormalizedSource
from app.providers.base import ModelProvider
from app.tools.knowledge.common import extraction_messages, validate_evidence


async def extract_facts(
    provider: ModelProvider,
    sources: list[NormalizedSource],
    objective: str,
    *,
    max_tokens: int | None = None,
) -> list[Fact]:
    response = await provider.structured_generate(
        extraction_messages(task="Extract explicit evidence-linked facts or claims as subject, predicate, and object. Return none when unsupported.", objective=objective, sources=sources),
        FactExtractionResponse,
        max_tokens=max_tokens,
    )
    validate_evidence(((fact.id, fact.evidence) for fact in response.facts), sources)
    return response.facts
