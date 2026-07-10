from __future__ import annotations

from processing_quality_agent.models.diagnosis import Diagnosis, FailureCategory
from processing_quality_agent.models.document import ParserRun
from processing_quality_agent.models.recovery import RecoveryPlan, RecoveryStrategy


def plan_recovery(
    diagnosis: Diagnosis,
    history: list[ParserRun],
    *,
    preferred_strategy: RecoveryStrategy | None = None,
    preferred_parser_id: str | None = None,
    max_per_parser: int = 1,
    max_total_attempts: int = 3,
) -> RecoveryPlan:
    if len(history) >= max_total_attempts:
        return RecoveryPlan(
            strategy=RecoveryStrategy.SEND_TO_HUMAN_REVIEW,
            rationale="Maximum total parser attempts exhausted.",
            exhausted=True,
        )
    if diagnosis.primary_failure == FailureCategory.UNSUPPORTED_FORMAT:
        return RecoveryPlan(
            strategy=RecoveryStrategy.REJECT_UNSUPPORTED,
            rationale=diagnosis.explanation,
            approval_required=True,
        )
    strategy = preferred_strategy
    if strategy is None:
        strategy = (
            RecoveryStrategy(diagnosis.eligible_strategies[0])
            if diagnosis.eligible_strategies
            else RecoveryStrategy.SEND_TO_HUMAN_REVIEW
        )
    current = history[-1] if history else None
    if strategy == RecoveryStrategy.RETRY_SAME_CONFIGURATION and current:
        identical = sum(
            run.parser_id == current.parser_id and run.parser_config == current.parser_config
            for run in history
        )
        if identical > max_per_parser:
            strategy = RecoveryStrategy.RETRY_WITH_ALTERNATE_PARSER
    return RecoveryPlan(
        strategy=strategy,
        parser_id=preferred_parser_id or (current.parser_id if current else None),
        rationale=f"Selected from governed strategies for {diagnosis.primary_failure.value}.",
    )
