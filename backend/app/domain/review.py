from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.assets import EvidenceReference, PropertyValue, QualityReport, ReviewStatus
from app.domain.runs import AssetPackageSummary


class AssetKind(StrEnum):
    ENTITIES = "entities"
    RELATIONSHIPS = "relationships"
    CONCEPTS = "concepts"
    FACTS = "facts"
    EVENTS = "events"


class AssetView(BaseModel):
    id: str
    kind: AssetKind
    name: str
    asset_type: str
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus
    evidence: list[EvidenceReference] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, PropertyValue] = Field(default_factory=dict)
    source_entity_id: str | None = None
    target_entity_id: str | None = None


class AssetPage(BaseModel):
    kind: AssetKind
    items: list[AssetView]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    available_types: list[str] = Field(default_factory=list)
    available_sources: list[str] = Field(default_factory=list)


class AssetOverview(BaseModel):
    package: AssetPackageSummary
    quality: QualityReport


class ReviewDecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1_000)


class ReviewDecisionResponse(BaseModel):
    asset: AssetView
    decision: ReviewStatus
