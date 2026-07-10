"""Explainable bounded representative sampling."""

from __future__ import annotations

import random
from collections import defaultdict

from source_readiness_agent.models.contracts import (
    SamplePolicy,
    SampleSelection,
    SamplingStrategy,
    SourceObject,
)


def select_sample(
    objects: list[SourceObject], policy: SamplePolicy, seed: int = 0
) -> list[SampleSelection]:
    if policy.strategy == SamplingStrategy.USER_SELECTED:
        candidates = objects
    elif policy.strategy == SamplingStrategy.RANDOM:
        candidates = random.Random(seed).sample(objects, min(len(objects), policy.maximum_files))
    else:
        by_ext: dict[str, list[SourceObject]] = defaultdict(list)
        for item in objects:
            by_ext[item.extension].append(item)
        ordered: list[SourceObject] = []
        # HYBRID starts with rare types, then size extremes, then fills common types.
        for _, group in sorted(by_ext.items(), key=lambda pair: (len(pair[1]), pair[0])):
            ordered.append(sorted(group, key=lambda item: item.file_size_bytes)[0])
        ordered.extend(sorted(objects, key=lambda item: item.file_size_bytes)[:2])
        ordered.extend(sorted(objects, key=lambda item: item.file_size_bytes, reverse=True)[:2])
        ordered.extend(objects)
        seen: set[str] = set()
        candidates = []
        for item in ordered:
            if item.object_id not in seen:
                seen.add(item.object_id)
                candidates.append(item)
    selected: list[SampleSelection] = []
    total = 0
    type_counts = {
        item.extension: sum(other.extension == item.extension for other in objects)
        for item in objects
    }
    sorted_sizes = sorted(item.file_size_bytes for item in objects)
    for item in candidates:
        if len(selected) >= policy.maximum_files:
            break
        if (
            item.file_size_bytes > policy.maximum_individual_file_size
            or total + item.file_size_bytes > policy.maximum_total_bytes
        ):
            continue
        reasons = []
        if type_counts.get(item.extension, 0) <= 2:
            reasons.append("rare file type")
        if sorted_sizes and item.file_size_bytes in {sorted_sizes[0], sorted_sizes[-1]}:
            reasons.append("size extreme")
        if not reasons:
            reasons.append("representative common file")
        selected.append(SampleSelection(source_object=item, reasons=reasons))
        total += item.file_size_bytes
    return selected
