from __future__ import annotations

from uuid import uuid4

from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import (
    AIJudgeResult,
    QualityAssessment,
    QualityDecision,
    QualityMetrics,
    QualityPolicy,
)
from processing_quality_agent.skills import (
    layout_quality,
    metadata_completeness,
    page_coverage,
    schema_validation,
    table_quality,
    text_quality,
)
from processing_quality_agent.skills.confidence_normalization import normalize_confidence


class QualityService:
    def __init__(self, policy: QualityPolicy | None = None) -> None:
        self.policy = policy or QualityPolicy()

    def evaluate(
        self, context: DocumentContext, ai_judge: AIJudgeResult | None = None
    ) -> QualityAssessment:
        evidence = [
            schema_validation.evaluate(context),
            page_coverage.evaluate(context),
            text_quality.evaluate(context),
            layout_quality.evaluate(context),
            table_quality.evaluate(context),
            metadata_completeness.evaluate(context),
        ]
        source_refs = context.silver_document.source_references if context.silver_document else []
        source_score = 1.0 if source_refs else 0.0
        evidence.append(
            type(evidence[0])(
                metric="source_reference_completeness",
                score=source_score,
                observations=[f"{len(source_refs)} source references"]
                if source_refs
                else ["No source references"],
            )
        )
        confidence = normalize_confidence(
            context.silver_document.parser_confidence if context.silver_document else None
        )
        evidence.append(
            type(evidence[0])(
                metric="normalized_parser_confidence",
                score=confidence,
                observations=[f"Normalized confidence {confidence:.2f}"],
            )
        )
        values: dict[str, float | None] = {item.metric: item.score for item in evidence}
        values["ai_judge_score"] = ai_judge.score if ai_judge else None
        metrics = QualityMetrics(**values)
        active_weights = {
            key: weight
            for key, weight in self.policy.weights.items()
            if key != "ai_judge_score" or ai_judge is not None
        }
        total_weight = sum(active_weights.values())
        score = (
            sum(float(getattr(metrics, key)) * weight for key, weight in active_weights.items())
            / total_weight
        )
        issues: list[str] = []
        run = context.parser_run
        if run and run.error_code:
            issues.append(run.error_code)
        if run and run.status in {"FAILED", "TIMEOUT"} and not run.error_code:
            issues.append("PARSER_SERVICE_ERROR")
        if metrics.page_coverage < 1:
            issues.append("PAGE_COVERAGE_FAILURE")
        if metrics.table_quality < 0.5:
            issues.append("TABLE_EXTRACTION_FAILURE")
        if metrics.text_quality < 0.3:
            issues.append("OCR_QUALITY_FAILURE")
        if metrics.schema_validity < 1:
            issues.append("SCHEMA_VALIDATION_FAILURE")
        if metrics.source_reference_completeness < 1:
            issues.append("SOURCE_REFERENCE_MISSING")
        if abs(confidence - score) >= self.policy.confidence_disagreement_threshold:
            issues.append("CONFIDENCE_DISAGREEMENT")
        hard = sorted(set(issues) & self.policy.blocking_failures)
        if hard:
            decision = (
                QualityDecision.REJECT_UNSUPPORTED
                if "UNSUPPORTED_FORMAT" in hard
                else QualityDecision.QUARANTINE
            )
        elif score >= self.policy.publish_threshold:
            decision = QualityDecision.PASS_WITH_WARNINGS if issues else QualityDecision.PASS
        elif score >= self.policy.warning_threshold:
            decision = QualityDecision.RETRY_SAME_PARSER
        elif score >= self.policy.human_review_threshold:
            decision = QualityDecision.RETRY_ALTERNATE_PARSER
        else:
            decision = QualityDecision.HUMAN_REVIEW
        return QualityAssessment(
            assessment_id=f"qa-{uuid4()}",
            document_id=context.manifest.document_id,
            run_id=context.parser_run.run_id
            if context.parser_run
            else context.manifest.current_run_id or "unknown",
            metrics=metrics,
            final_quality_score=score,
            issue_flags=issues,
            decision=decision,
            explanation=f"Deterministic governed quality score {score:.3f}; decision {decision.value}.",
            evidence=evidence,
            hard_failures=hard,
        )
