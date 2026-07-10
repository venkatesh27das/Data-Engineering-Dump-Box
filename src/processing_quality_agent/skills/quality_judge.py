from __future__ import annotations

from processing_quality_agent.models.quality import QualityMetrics, QualityPolicy


def should_trigger(
    metrics: QualityMetrics,
    deterministic_score: float,
    policy: QualityPolicy,
    *,
    document_class: str = "unknown",
    parsers_disagree: bool = False,
    complex_layout: bool = False,
    explicitly_requested: bool = False,
) -> bool:
    thresholds = (policy.publish_threshold, policy.warning_threshold, policy.human_review_threshold)
    near_threshold = any(
        abs(deterministic_score - threshold) <= policy.ai_judge_margin for threshold in thresholds
    )
    disagreement = (
        abs(metrics.normalized_parser_confidence - deterministic_score)
        >= policy.confidence_disagreement_threshold
    )
    ambiguous_tables = 0 < metrics.table_quality < 0.75
    return any(
        (
            explicitly_requested,
            near_threshold,
            disagreement,
            parsers_disagree,
            complex_layout,
            ambiguous_tables,
            document_class in policy.high_risk_classes,
        )
    )
