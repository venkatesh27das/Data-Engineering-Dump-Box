from processing_quality_agent.models.diagnosis import Diagnosis
from processing_quality_agent.models.document import ParserRun
from processing_quality_agent.models.recovery import RecoveryPlan, RecoveryStrategy
from processing_quality_agent.skills.recovery_planning import plan_recovery


class RecoveryService:
    def __init__(self, max_per_parser: int = 1, max_total_attempts: int = 3) -> None:
        self.max_per_parser = max_per_parser
        self.max_total_attempts = max_total_attempts

    def plan(
        self,
        diagnosis: Diagnosis,
        history: list[ParserRun],
        strategy: RecoveryStrategy | None = None,
        parser_id: str | None = None,
    ) -> RecoveryPlan:
        return plan_recovery(
            diagnosis,
            history,
            preferred_strategy=strategy,
            preferred_parser_id=parser_id,
            max_per_parser=self.max_per_parser,
            max_total_attempts=self.max_total_attempts,
        )
