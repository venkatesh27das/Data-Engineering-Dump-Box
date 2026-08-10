import re

from rapidfuzz.fuzz import ratio

from app.domain.assets import Entity
from app.domain.extraction import AmbiguousEntityMatch, EntityMerge, EntityResolutionResult


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _names(entity: Entity) -> set[str]:
    return {_normalized(entity.canonical_name), *(_normalized(alias) for alias in entity.aliases)} - {""}


def _merge(canonical: Entity, duplicate: Entity) -> Entity:
    aliases = list(dict.fromkeys([*canonical.aliases, duplicate.canonical_name, *duplicate.aliases]))
    aliases = [alias for alias in aliases if _normalized(alias) != _normalized(canonical.canonical_name)]
    evidence = list({reference.model_dump_json(): reference for reference in [*canonical.evidence, *duplicate.evidence]}.values())
    attributes = {**duplicate.attributes, **canonical.attributes}
    return canonical.model_copy(update={"aliases": aliases, "evidence": evidence, "attributes": attributes, "confidence": max(canonical.confidence, duplicate.confidence)})


def resolve_entities(entities: list[Entity], *, merge_threshold: float = 0.94, ambiguity_threshold: float = 0.82) -> EntityResolutionResult:
    resolved: list[Entity] = []
    redirects: dict[str, str] = {}
    merges: list[EntityMerge] = []
    ambiguous: list[AmbiguousEntityMatch] = []
    for entity in entities:
        best: tuple[int, Entity] | None = None
        exact = False
        entity_names = _names(entity)
        for candidate in resolved:
            candidate_names = _names(candidate)
            if entity_names & candidate_names:
                best = (100, candidate)
                exact = True
                break
            score = max((ratio(left, right) for left in entity_names for right in candidate_names), default=0)
            if best is None or score > best[0]:
                best = (score, candidate)
        if best and (exact or best[0] / 100 >= merge_threshold) and best[1].entity_type.lower() == entity.entity_type.lower():
            index = resolved.index(best[1])
            resolved[index] = _merge(best[1], entity)
            redirects[entity.id] = best[1].id
            merges.append(EntityMerge(canonical_entity_id=best[1].id, merged_entity_ids=[entity.id], method="exact_or_alias" if exact else "deterministic_similarity", score=best[0] / 100))
        else:
            if best and best[0] / 100 >= ambiguity_threshold:
                ambiguous.append(AmbiguousEntityMatch(entity_id=entity.id, candidate_entity_id=best[1].id, score=best[0] / 100))
            resolved.append(entity)
    return EntityResolutionResult(entities=resolved, redirects=redirects, merges=merges, ambiguous_matches=ambiguous)
