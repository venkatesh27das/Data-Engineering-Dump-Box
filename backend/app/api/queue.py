from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.config import Settings, get_settings
from app.domain.runs import RunDetail, RunLineageEdge, RunQueueItem, RunStatus
from app.repositories.projects import ProjectRepository, SourceRepository
from app.repositories.runs import AssetPackageRepository, RunArtifactRepository, RunRepository
from app.services.task_manager import task_manager
from app.storage.database import Database, get_database


router = APIRouter(prefix="/runs", tags=["run-queue"])


def _reconcile_orphaned_runs(database: Database, settings: Settings) -> None:
    """Make persisted state truthful after an API process restart."""
    repository = RunRepository(database)
    packages = AssetPackageRepository(database, settings.artifact_path)
    for run in repository.list_active():
        if task_manager.is_active(run.id):
            continue
        package = packages.summary_for_run(run.id)
        if package is not None:
            repository.update(
                run.id,
                status=RunStatus.COMPLETED,
                current_stage="completed",
                package_id=package.package_id,
                completed=True,
            )
            repository.add_event(
                run.id,
                stage="completed",
                status="completed",
                title="Completed package recovered",
                message="The generated package was recovered after the API process restarted.",
                event_type="run",
            )
            continue
        repository.update(
            run.id,
            status=RunStatus.FAILED,
            current_stage="interrupted",
            error_message="The API process restarted before this background run completed",
            completed=True,
        )
        repository.add_event(
            run.id,
            stage="interrupted",
            status="failed",
            title="Process interrupted",
            message="The API process restarted before this background run completed. Start a new run to retry.",
            event_type="run",
        )


def _queue_item(run_id: str, database: Database, settings: Settings) -> RunQueueItem:
    run = RunRepository(database).get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    project = ProjectRepository(database).get(run.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Run project not found")
    return RunQueueItem(
        run=run,
        project_name=project.name,
        source_count=len(SourceRepository(database).list_for_project(run.project_id)),
        event_count=len(RunRepository(database).list_events(run_id)),
        artifact_count=len(RunArtifactRepository(database).list_for_run(run_id)),
        package=AssetPackageRepository(database, settings.artifact_path).summary_for_run(run_id),
    )


@router.get("", response_model=list[RunQueueItem])
async def list_run_queue(
    run_status: RunStatus | None = Query(default=None, alias="status"),
    project_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> list[RunQueueItem]:
    _reconcile_orphaned_runs(database, settings)
    return RunRepository(database).list_queue(status=run_status, project_id=project_id, limit=limit)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run_detail(
    run_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> RunDetail:
    _reconcile_orphaned_runs(database, settings)
    item = _queue_item(run_id, database, settings)
    artifacts = RunArtifactRepository(database).list_for_run(run_id)
    source_ids = {source.id for source in SourceRepository(database).list_for_project(item.run.project_id)}
    lineage = [
        RunLineageEdge(
            parent_id=parent_id,
            child_id=artifact.id,
            relationship="normalized_from" if parent_id in source_ids else "derived_from",
        )
        for artifact in artifacts
        for parent_id in artifact.parent_ids
    ]
    return RunDetail(
        item=item,
        sources=SourceRepository(database).list_for_project(item.run.project_id),
        events=RunRepository(database).list_events(run_id),
        temporary_assets=artifacts,
        lineage=lineage,
    )


@router.post("/{run_id}/cancel", response_model=RunQueueItem)
async def cancel_run(
    run_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> RunQueueItem:
    _reconcile_orphaned_runs(database, settings)
    repository = RunRepository(database)
    run = repository.get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
        raise HTTPException(status_code=409, detail="Only queued or running processes can be canceled")
    await task_manager.cancel_and_wait(run_id)
    repository.update(
        run_id,
        status=RunStatus.CANCELED,
        current_stage="canceled",
        error_message="Canceled by user",
        completed=True,
    )
    repository.add_event(
        run_id,
        stage="canceled",
        status="canceled",
        title="Process canceled",
        message="Execution was stopped by the user. Generated temporary records remain available until deletion.",
        event_type="run",
    )
    return _queue_item(run_id, database, settings)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    _reconcile_orphaned_runs(database, settings)
    repository = RunRepository(database)
    run = repository.get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in {RunStatus.QUEUED, RunStatus.RUNNING} or task_manager.is_active(run_id):
        raise HTTPException(status_code=409, detail="Cancel the process before deleting it")
    try:
        AssetPackageRepository(database, settings.artifact_path).delete_for_run(run_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    repository.delete(run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
