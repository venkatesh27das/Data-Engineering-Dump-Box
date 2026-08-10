from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.domain.publication import Publication, PublicationStatusResponse
from app.graph.base import GraphStore, GraphStoreError, GraphStoreNotConfigured
from app.graph.dependencies import get_graph_store
from app.repositories.projects import ProjectRepository
from app.repositories.publications import PublicationRepository
from app.repositories.runs import AssetPackageRepository
from app.storage.database import Database, get_database

router = APIRouter(prefix="/projects/{project_id}/publish", tags=["publication"])


@router.post("/neo4j", response_model=Publication, status_code=status.HTTP_201_CREATED)
async def publish_to_neo4j(
    project_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
    graph_store: GraphStore = Depends(get_graph_store),
) -> Publication:
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    package = AssetPackageRepository(database, settings.artifact_path).load_latest(project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="No generated asset package found")
    if not graph_store.configured:
        raise HTTPException(status_code=409, detail="Configure Neo4j Aura credentials before publishing")
    repository = PublicationRepository(database)
    publication = repository.create(project_id, package.package_id)
    try:
        result = await graph_store.publish_package(package)
    except GraphStoreNotConfigured as error:
        repository.fail(publication.id, str(error))
        raise HTTPException(status_code=409, detail="Configure Neo4j Aura credentials before publishing") from error
    except GraphStoreError as error:
        repository.fail(publication.id, str(error))
        raise HTTPException(status_code=502, detail="Neo4j publication failed; check connection status and publication history") from error
    return repository.complete(publication.id, result)


@router.get("/status", response_model=PublicationStatusResponse)
async def get_publication_status(
    project_id: str,
    database: Database = Depends(get_database),
    graph_store: GraphStore = Depends(get_graph_store),
) -> PublicationStatusResponse:
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    repository = PublicationRepository(database)
    connected = await graph_store.health_check() if graph_store.configured else False
    return PublicationStatusResponse(configured=graph_store.configured, connected=connected, latest=repository.latest(project_id), history=repository.list_for_project(project_id))
