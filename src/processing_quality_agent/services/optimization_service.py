from __future__ import annotations

import yaml

from processing_quality_agent.models.responses import ParserComparison


class OptimizationService:
    def propose(self, document_class: str, comparison: ParserComparison) -> str:
        ordered = [item.parser_id for item in comparison.rankings]
        policy = {
            "document_class": document_class,
            "primary_parser": ordered[0] if ordered else None,
            "fallback_parser": ordered[1] if len(ordered) > 1 else None,
            "eligibility": {"mime_types": ["application/pdf"]},
            "quality_thresholds": {"publish": 0.85, "human_review": 0.65},
            "retry": {"max_same_parser": 1, "max_total_attempts": 3},
            "approval": {"required": True},
        }
        return yaml.safe_dump(policy, sort_keys=False)
