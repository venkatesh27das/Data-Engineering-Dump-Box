import json
from collections.abc import Iterable

from app.domain.assets import EvidenceReference
from app.domain.normalized import NormalizedSource
from app.providers.base import ChatMessage, ModelProvider, StructuredModel


class KnowledgeToolError(ValueError):
    pass


def _serialized(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _compact_source(source: NormalizedSource, *, character_budget: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "modality": source.modality,
        "source_type": source.source_type,
        "parsing_confidence": source.parsing_confidence,
        "warnings": source.warnings,
    }

    if source.modality == "structured":
        tables = [table.model_dump(mode="json") for table in source.tables]
        payload["tables"] = tables
        while len(_serialized(payload)) > character_budget and tables:
            if len(tables) > 1:
                tables.pop()
                continue
            columns = tables[0].get("columns", [])
            if isinstance(columns, list) and len(columns) > 1:
                columns.pop()
                continue
            tables.pop()
        if len(tables) < len(source.tables):
            payload["truncated"] = True
        return payload

    if source.chunks:
        text_items = [
            {
                "id": chunk.id,
                "text": chunk.text,
                "page": chunk.page,
                "section": chunk.section,
            }
            for chunk in source.chunks[:12]
        ]
        payload["chunks"] = text_items
    elif source.pages:
        text_items = [
            {"page_number": page.page_number, "text": page.text}
            for page in source.pages
        ]
        payload["pages"] = text_items
    else:
        text_items = [{"text": source.text}]
        payload["content"] = text_items

    content_key = "chunks" if "chunks" in payload else "pages" if "pages" in payload else "content"
    while len(_serialized(payload)) > character_budget and len(text_items) > 1:
        text_items.pop()
    text_was_truncated = False
    if len(_serialized(payload)) > character_budget and text_items:
        text = str(text_items[0].get("text", ""))
        overhead = len(_serialized(payload)) - len(text)
        shortened_text = text[: max(0, character_budget - overhead - 20)]
        text_items[0]["text"] = shortened_text
        text_was_truncated = len(shortened_text) < len(text)
    expected_items = len(source.chunks[:12]) if source.chunks else len(source.pages) if source.pages else 1
    if text_was_truncated or len(text_items) < expected_items or len(source.chunks) > 12:
        payload["truncated"] = True
    if not text_items:
        payload.pop(content_key, None)
    return payload


def source_context(sources: list[NormalizedSource], *, max_characters: int = 24_000) -> str:
    payloads: list[dict[str, object]] = []
    remaining = max(0, max_characters - 2)  # Reserve the enclosing JSON list brackets.
    for index, source in enumerate(sources):
        sources_left = len(sources) - index
        character_budget = max(256, remaining // sources_left)
        payload = _compact_source(source, character_budget=character_budget)
        serialized = _serialized(payload)
        separator_characters = 2 if payloads else 0
        if len(serialized) + separator_characters > remaining:
            break
        payloads.append(payload)
        remaining -= len(serialized) + separator_characters
    return _serialized(payloads)


def extraction_messages(*, task: str, objective: str, sources: list[NormalizedSource], extra_context: str = "") -> list[ChatMessage]:
    system = (
        "You are a knowledge engineer producing schema-constrained graph assets. "
        "Use only supplied source content. Every material asset must have at least one evidence reference "
        "with a valid source_id and confidence between 0 and 1. An empty result is valid only when the "
        "supplied sources contain no evidence for the requested asset type. When present, identify named "
        "parties, agreements, products, services, identifiers, dates, prices, obligations, delivery terms, "
        "and payment terms. Do not invent facts or hidden reasoning."
    )
    user = f"Knowledge objective:\n{objective}\n\nTask:\n{task}\n\nSources:\n{source_context(sources)}"
    if extra_context:
        user += f"\n\nExisting typed context:\n{extra_context}"
    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]


def has_meaningful_source_content(sources: list[NormalizedSource], *, minimum_characters: int = 40) -> bool:
    for source in sources:
        if source.tables:
            return True
        text = source.text or " ".join(chunk.text for chunk in source.chunks) or " ".join(page.text for page in source.pages)
        if len(text.strip()) >= minimum_characters:
            return True
    return False


async def generate_required_collection(
    provider: ModelProvider,
    messages: list[ChatMessage],
    response_model: type[StructuredModel],
    *,
    collection_field: str,
    asset_description: str,
    sources: list[NormalizedSource],
    max_tokens: int | None = None,
) -> StructuredModel:
    response = await provider.structured_generate(messages, response_model, max_tokens=max_tokens)
    if getattr(response, collection_field) or not has_meaningful_source_content(sources):
        return response

    retry_messages = [
        *messages,
        ChatMessage(
            role="user",
            content=(
                f"Your previous response returned no {collection_field}, but the supplied source contains "
                f"material business content. Re-read every source chunk and extract supported {asset_description}. "
                "Return an empty collection only if none are evidenced. Preserve exact source_id values and "
                "include at least one evidence reference for every extracted asset."
            ),
        ),
    ]
    response = await provider.structured_generate(retry_messages, response_model, max_tokens=max_tokens)
    if not getattr(response, collection_field):
        raise KnowledgeToolError(
            f"LM Studio returned no {collection_field} for meaningful source content after one extraction retry"
        )
    return response


def validate_evidence(asset_evidence: Iterable[tuple[str, list[EvidenceReference]]], sources: list[NormalizedSource]) -> None:
    source_ids = {source.source_id for source in sources}
    for asset_id, evidence in asset_evidence:
        if not evidence:
            raise KnowledgeToolError(f"Asset {asset_id} is missing provenance")
        invalid = {reference.source_id for reference in evidence if reference.source_id not in source_ids}
        if invalid:
            raise KnowledgeToolError(f"Asset {asset_id} references unknown sources: {', '.join(sorted(invalid))}")
