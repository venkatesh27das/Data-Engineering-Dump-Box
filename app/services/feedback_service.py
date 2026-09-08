from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.assets import Feedback
from app.models.region import RegionType
from app.models.run import now
from app.storage.metadata_store import MetadataStore


class FeedbackRequest(BaseModel):
    content: str = Field(default="", max_length=4000)
    expected_region_type: RegionType | None = None


class ReprocessRequest(FeedbackRequest):
    use_agent: bool = False


class FeedbackService:
    def __init__(self, metadata: MetadataStore):
        self.metadata = metadata

    def submit(self, region_id: str, request: FeedbackRequest) -> Feedback:
        _, run_id, _ = self.metadata.region_context(region_id)
        record = Feedback(
            feedback_id=uuid4().hex,
            region_id=region_id,
            run_id=run_id,
            content=request.content,
            expected_region_type=request.expected_region_type,
            created_at=now().isoformat(),
        )
        self.metadata.save_feedback(record)
        return record


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=10, ge=1, le=20)
    run_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
