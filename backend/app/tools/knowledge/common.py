import json
from collections.abc import Iterable

from app.domain.assets import EvidenceReference
from app.domain.normalized import NormalizedSource
from app.providers.base import ChatMessage


class KnowledgeToolError(ValueError):
    pass


def source_context(sources: list[NormalizedSource], *, max_characters: int = 60_000) -> str:
    payloads: list[dict[str, object]] = []
    remaining = max_characters
    for source in sources:
        payload = source.model_dump(mode="json")
        serialized = json.dumps(payload, ensure_ascii=False)
        if len(serialized) > remaining:
            payload["text"] = str(payload.get("text", ""))[: max(0, remaining // 2)]
            payload["chunks"] = list(payload.get("chunks", []))[:10]  # type: ignore[arg-type]
            serialized = json.dumps(payload, ensure_ascii=False)
        if len(serialized) > remaining:
            break
        payloads.append(payload)
        remaining -= len(serialized)
    return json.dumps(payloads, ensure_ascii=False)


def extraction_messages(*, task: str, objective: str, sources: list[NormalizedSource], extra_context: str = "") -> list[ChatMessage]:
    system = (
        "You are a knowledge engineer producing schema-constrained graph assets. "
        "Use only supplied source content. Every material asset must have at least one evidence reference "
        "with a valid source_id and confidence between 0 and 1. Do not invent facts or hidden reasoning."
    )
    user = f"Knowledge objective:\n{objective}\n\nTask:\n{task}\n\nSources:\n{source_context(sources)}"
    if extra_context:
        user += f"\n\nExisting typed context:\n{extra_context}"
    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]


def validate_evidence(asset_evidence: Iterable[tuple[str, list[EvidenceReference]]], sources: list[NormalizedSource]) -> None:
    source_ids = {source.source_id for source in sources}
    for asset_id, evidence in asset_evidence:
        if not evidence:
            raise KnowledgeToolError(f"Asset {asset_id} is missing provenance")
        invalid = {reference.source_id for reference in evidence if reference.source_id not in source_ids}
        if invalid:
            raise KnowledgeToolError(f"Asset {asset_id} references unknown sources: {', '.join(sorted(invalid))}")
