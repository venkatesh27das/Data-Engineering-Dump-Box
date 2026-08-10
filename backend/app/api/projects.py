from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.config import Settings, get_settings
from app.domain.projects import Project, ProjectCreate, ProjectUpdate, SourceAsset
from app.repositories.projects import ProjectRepository, SourceRepository
from app.services.uploads import UploadService, UploadValidationError
from app.storage.database import Database, get_database

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    database: Database = Depends(get_database),
) -> Project:
    return ProjectRepository(database).create(payload)


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    database: Database = Depends(get_database),
) -> Project:
    project = ProjectRepository(database).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    database: Database = Depends(get_database),
) -> Project:
    project = ProjectRepository(database).update(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_id}/sources",
    response_model=SourceAsset,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    project_id: str,
    file: UploadFile = File(...),
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> SourceAsset:
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    service = UploadService(settings, SourceRepository(database))
    try:
        return await service.save(project_id, file)
    except UploadValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{project_id}/sources", response_model=list[SourceAsset])
async def list_sources(
    project_id: str,
    database: Database = Depends(get_database),
) -> list[SourceAsset]:
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return SourceRepository(database).list_for_project(project_id)


@router.delete("/{project_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    project_id: str,
    source_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    service = UploadService(settings, SourceRepository(database))
    try:
        removed = service.remove(project_id, source_id)
    except UploadValidationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if removed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
