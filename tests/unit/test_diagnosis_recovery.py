from processing_quality_agent.models.diagnosis import Diagnosis, FailureCategory
from processing_quality_agent.models.document import ParserRun
from processing_quality_agent.models.recovery import RecoveryStrategy
from processing_quality_agent.services.quality_service import QualityService
from processing_quality_agent.skills.failure_diagnosis import diagnose
from processing_quality_agent.skills.recovery_planning import plan_recovery
from processing_quality_agent.tools.mock_repository import default_contexts


def test_missing_table_diagnosis():
    context = default_contexts()["DOC-102"]
    result = diagnose(context, QualityService().evaluate(context))
    assert result.primary_failure == FailureCategory.TABLE_EXTRACTION_FAILURE
    assert "TABLE_FOCUSED_REPROCESS" in result.eligible_strategies


def test_retry_exhaustion_escalates():
    diagnosis = Diagnosis(
        primary_failure=FailureCategory.PARSER_TIMEOUT,
        severity="MEDIUM",
        retryable=True,
        explanation="timeout",
        eligible_strategies=["RETRY_SAME_CONFIGURATION"],
    )
    history = [
        ParserRun(run_id=str(i), document_id="D", parser_id="p", status="FAILED") for i in range(3)
    ]
    plan = plan_recovery(diagnosis, history, max_total_attempts=3)
    assert plan.strategy == RecoveryStrategy.SEND_TO_HUMAN_REVIEW
    assert plan.exhausted


def test_no_identical_retry_loop():
    diagnosis = Diagnosis(
        primary_failure=FailureCategory.PARSER_TIMEOUT,
        severity="MEDIUM",
        retryable=True,
        explanation="timeout",
        eligible_strategies=["RETRY_SAME_CONFIGURATION"],
    )
    history = [
        ParserRun(
            run_id="1", document_id="D", parser_id="p", parser_config={"ocr": True}, status="FAILED"
        ),
        ParserRun(
            run_id="2", document_id="D", parser_id="p", parser_config={"ocr": True}, status="FAILED"
        ),
    ]
    plan = plan_recovery(
        diagnosis,
        history,
        preferred_strategy=RecoveryStrategy.RETRY_SAME_CONFIGURATION,
        max_per_parser=1,
    )
    assert plan.strategy == RecoveryStrategy.RETRY_WITH_ALTERNATE_PARSER
