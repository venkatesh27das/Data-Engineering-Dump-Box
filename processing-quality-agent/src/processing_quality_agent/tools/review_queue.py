from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from processing_quality_agent.models.document import utc_now


class HumanReviewRequest(BaseModel):
    review_id: str
    document_id: str
    run_id: str
    issue_type: str
    severity: str
    issue_summary: str
    evidence: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    recommended_action: str
    parser_comparison: dict[str, Any] | None = None
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    status: str = "OPEN"


class ReviewQueueRepository(Protocol):
    async def submit(self, request: HumanReviewRequest) -> HumanReviewRequest: ...


class InMemoryReviewQueue:
    def __init__(self) -> None:
        self.items: dict[str, HumanReviewRequest] = {}

    async def submit(self, request: HumanReviewRequest) -> HumanReviewRequest:
        if request.review_id not in self.items:
            self.items[request.review_id] = request
        return self.items[request.review_id]
