from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PropertyValue = str | int | float | bool | None


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REVIEW = "review"
    NEEDS_ATTENTION = "needs_attention"
    REJECTED = "rejected"


class EvidenceReference(BaseModel):
    source_id: str
    source_name: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    chunk_id: str | None = None
    table: str | None = None
    column: str | None = None
    excerpt: str | None = Field(default=None, max_length=2_000)


class Entity(BaseModel):
    id: str
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, PropertyValue] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING


class Relationship(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING

    @model_validator(mode="after")
    def disallow_self_reference(self) -> "Relationship":
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("A relationship cannot connect an entity to itself")
        return self


class Concept(BaseModel):
    id: str
    name: str
    definition: str
    broader_concept_id: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING


class Fact(BaseModel):
    id: str
    subject: str
    predicate: str
    object: str
    qualifiers: dict[str, PropertyValue] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING


class Event(BaseModel):
    id: str
    name: str
    event_type: str
    occurred_at: datetime | None = None
    participants: list[str] = Field(default_factory=list)
    attributes: dict[str, PropertyValue] = Field(default_factory=dict)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING


class SemanticMapping(BaseModel):
    id: str
    source_term: str
    target_concept_id: str
    mapping_type: Literal["exact", "close", "broader", "narrower", "related"]
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_status: ReviewStatus = ReviewStatus.PENDING


class GraphPropertyDefinition(BaseModel):
    name: str
    data_type: str
    required: bool = False


class GraphNodeDefinition(BaseModel):
    label: str
    key_property: str = "asset_id"
    properties: list[GraphPropertyDefinition] = Field(default_factory=list)


class GraphRelationshipDefinition(BaseModel):
    relationship_type: str
    source_label: str
    target_label: str
    properties: list[GraphPropertyDefinition] = Field(default_factory=list)


class GraphSchema(BaseModel):
    node_definitions: list[GraphNodeDefinition] = Field(default_factory=list)
    relationship_definitions: list[GraphRelationshipDefinition] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class QualityDisposition(StrEnum):
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    FAIL = "FAIL"


class QualityIssue(BaseModel):
    id: str
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    asset_id: str | None = None
    source_id: str | None = None


class QualityReport(BaseModel):
    overall_score: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    average_confidence: float = Field(ge=0, le=1)
    consistency: float = Field(ge=0, le=1)
    completeness: float = Field(ge=0, le=1)
    duplicate_rate: float = Field(default=0, ge=0, le=1)
    unresolved_references: int = Field(default=0, ge=0)
    disposition: QualityDisposition
    issues: list[QualityIssue] = Field(default_factory=list)


class KnowledgeAssetPackage(BaseModel):
    package_id: str
    project_id: str
    sources: list["SourceAsset"]
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    semantic_mappings: list[SemanticMapping] = Field(default_factory=list)
    graph_schema: GraphSchema
    quality_report: QualityReport
    created_at: datetime

    @model_validator(mode="after")
    def validate_references(self) -> "KnowledgeAssetPackage":
        entity_ids = {entity.id for entity in self.entities}
        invalid = [
            relationship.id
            for relationship in self.relationships
            if relationship.source_entity_id not in entity_ids
            or relationship.target_entity_id not in entity_ids
        ]
        if invalid:
            raise ValueError(f"Relationships reference missing entities: {', '.join(invalid)}")
        return self


from app.domain.projects import SourceAsset  # noqa: E402

KnowledgeAssetPackage.model_rebuild()
