from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .document import utc_now


class RecoveryStrategy(StrEnum):
    NO_ACTION = "NO_ACTION"
    RETRY_SAME_CONFIGURATION = "RETRY_SAME_CONFIGURATION"
    RETRY_WITH_CONFIGURATION_CHANGE = "RETRY_WITH_CONFIGURATION_CHANGE"
    RETRY_WITH_ALTERNATE_PARSER = "RETRY_WITH_ALTERNATE_PARSER"
    OCR_ENHANCED_REPROCESS = "OCR_ENHANCED_REPROCESS"
    PAGE_RANGE_REPROCESS = "PAGE_RANGE_REPROCESS"
    TABLE_FOCUSED_REPROCESS = "TABLE_FOCUSED_REPROCESS"
    SEND_TO_HUMAN_REVIEW = "SEND_TO_HUMAN_REVIEW"
    QUARANTINE = "QUARANTINE"
    REJECT_UNSUPPORTED = "REJECT_UNSUPPORTED"


class ApprovalContext(BaseModel):
    approved: bool = False
    approval_reference: str | None = None
    approved_by: str | None = None

    def valid(self) -> bool:
        return bool(self.approved and self.approval_reference and self.approved_by)


class RecoveryPlan(BaseModel):
    strategy: RecoveryStrategy
    parser_id: str | None = None
    parser_config: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    approval_required: bool = True
    exhausted: bool = False


class RecoveryAttempt(BaseModel):
    recovery_id: str
    document_id: str
    source_run_id: str
    recovery_run_id: str | None = None
    strategy: RecoveryStrategy
    parser_id: str | None = None
    parser_config: dict[str, Any] = Field(default_factory=dict)
    approval_reference: str
    actor: str
    status: str
    before_quality_score: float | None = None
    after_quality_score: float | None = None
    outcome: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
