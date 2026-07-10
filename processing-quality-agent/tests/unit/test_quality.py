from processing_quality_agent.models.quality import AIJudgeResult, QualityPolicy
from processing_quality_agent.services.quality_service import QualityService
from processing_quality_agent.skills.confidence_normalization import normalize_confidence
from processing_quality_agent.skills.quality_judge import should_trigger
from processing_quality_agent.tools.mock_repository import default_contexts


def test_quality_detects_missing_required_table():
    assessment = QualityService().evaluate(default_contexts()["DOC-102"])
    assert "TABLE_EXTRACTION_FAILURE" in assessment.issue_flags
    assert assessment.metrics.table_quality == 0
    assert assessment.final_quality_score < 1


def test_ai_weight_is_redistributed_and_judge_changes_score():
    context = default_contexts()["DOC-102"]
    service = QualityService()
    without = service.evaluate(context)
    judge = AIJudgeResult(
        score=0,
        decision="FAIL",
        explanation="missing table",
        uncertainty="low",
        recommended_action="retry",
    )
    with_judge = service.evaluate(context, judge)
    assert with_judge.final_quality_score < without.final_quality_score


def test_hard_failure_overrides_numeric_score():
    context = default_contexts()["DOC-102"]
    context.parser_run.error_code = "CORRUPT_FILE"
    assessment = QualityService().evaluate(context)
    assert "CORRUPT_FILE" in assessment.hard_failures
    assert assessment.decision.value == "QUARANTINE"


def test_confidence_normalization():
    assert normalize_confidence(92) == 0.92
    assert normalize_confidence(None) == 0.5
    assert normalize_confidence(2) == 0.02


def test_ai_judge_trigger_on_conflict():
    assessment = QualityService().evaluate(default_contexts()["DOC-102"])
    assessment.metrics.normalized_parser_confidence = 1
    assert should_trigger(assessment.metrics, 0.4, QualityPolicy())
