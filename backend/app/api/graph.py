from fastapi import APIRouter, Depends, HTTPException

from app.domain.graph import CypherQueryRequest, CypherQueryResponse, GraphCounts, GraphNodeDetail, GraphResponse
from app.graph.base import GraphStore, GraphStoreError, GraphStoreNotConfigured
from app.graph.dependencies import get_graph_store
from app.repositories.projects import ProjectRepository
from app.services.cypher_guard import validate_read_only_cypher
from app.storage.database import Database, get_database

router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


def _require_project(project_id: str, database: Database) -> None:
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _graph_error(error: GraphStoreError) -> HTTPException:
    if isinstance(error, GraphStoreNotConfigured):
        return HTTPException(status_code=409, detail="Configure Neo4j Aura before exploring the graph")
    return HTTPException(status_code=502, detail=str(error))


@router.get("", response_model=GraphResponse)
async def get_graph(project_id: str, database: Database = Depends(get_database), graph_store: GraphStore = Depends(get_graph_store)) -> GraphResponse:
    _require_project(project_id, database)
    try:
        graph = await graph_store.get_subgraph(project_id)
    except GraphStoreError as error:
        raise _graph_error(error) from error
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_types = {str(node["data"]["type"]) for node in nodes}  # type: ignore[index]
    relationship_types = {str(edge["data"]["label"]) for edge in edges}  # type: ignore[index]
    return GraphResponse.model_validate({"nodes": nodes, "edges": edges, "counts": GraphCounts(nodes=len(nodes), relationships=len(edges), node_types=len(node_types), relationship_types=len(relationship_types))})


@router.get("/node/{node_id}", response_model=GraphNodeDetail)
async def get_graph_node(project_id: str, node_id: str, database: Database = Depends(get_database), graph_store: GraphStore = Depends(get_graph_store)) -> GraphNodeDetail:
    _require_project(project_id, database)
    try:
        node = await graph_store.get_node(project_id, node_id)
    except GraphStoreError as error:
        raise _graph_error(error) from error
    if node is None:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return GraphNodeDetail.model_validate(node)


@router.post("/query", response_model=CypherQueryResponse)
async def run_graph_query(payload: CypherQueryRequest, project_id: str, database: Database = Depends(get_database), graph_store: GraphStore = Depends(get_graph_store)) -> CypherQueryResponse:
    _require_project(project_id, database)
    try:
        query = validate_read_only_cypher(payload.query)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    parameters = {**payload.parameters, "project_id": project_id}
    try:
        rows = await graph_store.query(project_id, query, parameters)
    except GraphStoreError as error:
        raise _graph_error(error) from error
    return CypherQueryResponse(rows=rows, row_count=len(rows))
