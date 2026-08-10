from pydantic import BaseModel, Field

from app.domain.assets import Concept, Entity, Event, Fact, Relationship, SemanticMapping


class EntityExtractionResponse(BaseModel):
    entities: list[Entity] = Field(default_factory=list)


class RelationshipExtractionResponse(BaseModel):
    relationships: list[Relationship] = Field(default_factory=list)


class ConceptDiscoveryResponse(BaseModel):
    concepts: list[Concept] = Field(default_factory=list)


class FactExtractionResponse(BaseModel):
    facts: list[Fact] = Field(default_factory=list)


class EventExtractionResponse(BaseModel):
    events: list[Event] = Field(default_factory=list)


class SemanticMappingResponse(BaseModel):
    semantic_mappings: list[SemanticMapping] = Field(default_factory=list)


class EntityMerge(BaseModel):
    canonical_entity_id: str
    merged_entity_ids: list[str]
    method: str
    score: float = Field(ge=0, le=1)


class AmbiguousEntityMatch(BaseModel):
    entity_id: str
    candidate_entity_id: str
    score: float = Field(ge=0, le=1)


class EntityResolutionResult(BaseModel):
    entities: list[Entity]
    redirects: dict[str, str] = Field(default_factory=dict)
    merges: list[EntityMerge] = Field(default_factory=list)
    ambiguous_matches: list[AmbiguousEntityMatch] = Field(default_factory=list)
