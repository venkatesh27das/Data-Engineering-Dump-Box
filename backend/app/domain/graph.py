from pydantic import BaseModel, Field


class CytoscapeNodeData(BaseModel):
    id: str
    label: str
    type: str
    confidence: float | None = None
    sources: list[str] = Field(default_factory=list)
    search_text: str = ""


class CytoscapeNode(BaseModel):
    data: CytoscapeNodeData


class CytoscapeEdgeData(BaseModel):
    id: str
    source: str
    target: str
    label: str
    confidence: float | None = None
    search_text: str = ""


class CytoscapeEdge(BaseModel):
    data: CytoscapeEdgeData


class GraphCounts(BaseModel):
    nodes: int = Field(ge=0)
    relationships: int = Field(ge=0)
    node_types: int = Field(ge=0)
    relationship_types: int = Field(ge=0)


class GraphResponse(BaseModel):
    nodes: list[CytoscapeNode]
    edges: list[CytoscapeEdge]
    counts: GraphCounts


class NodeRelationship(BaseModel):
    id: str
    type: str
    direction: str
    other_node_id: str
    other_node_label: str
    confidence: float | None = None


class GraphNodeDetail(BaseModel):
    id: str
    name: str
    type: str
    labels: list[str] = Field(default_factory=list)
    confidence: float | None = None
    description: str | None = None
    sources: list[str] = Field(default_factory=list)
    properties: dict[str, object] = Field(default_factory=dict)
    evidence: list[dict[str, object]] = Field(default_factory=list)
    relationships: list[NodeRelationship] = Field(default_factory=list)


class CypherQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5_000)
    parameters: dict[str, object] = Field(default_factory=dict)


class CypherQueryResponse(BaseModel):
    rows: list[dict[str, object]]
    row_count: int = Field(ge=0)
