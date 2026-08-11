import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.domain.runs import AgentEvent, Run, RunStatus
from app.orchestration import RunOrchestrator
from app.providers.base import ModelProvider
from app.providers.dependencies import get_model_provider
from app.repositories.projects import ProjectRepository, SourceRepository
from app.repositories.runs import RunRepository
from app.services.task_manager import task_manager
from app.storage.database import Database, get_database

router = APIRouter(prefix="/projects/{project_id}/runs", tags=["runs"])


@router.post("", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    project_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> Run:
    project = ProjectRepository(database).get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sources = SourceRepository(database).list_for_project(project_id)
    if not sources:
        raise HTTPException(status_code=400, detail="Upload at least one source before starting a run")
    repository = RunRepository(database)
    run = repository.create(project_id)
    repository.add_event(run.id, stage="queued", status="queued", title="Run queued", message="Knowledge Asset Supervisor will start shortly", event_type="run")
    task_manager.start(
        run.id,
        lambda: RunOrchestrator(database=database, settings=settings, provider=provider).execute(
            run_id=run.id,
            project=project,
            sources=sources,
        ),
    )
    return run


@router.get("/{run_id}", response_model=Run)
async def get_run(project_id: str, run_id: str, database: Database = Depends(get_database)) -> Run:
    run = RunRepository(database).get(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/events", response_model=list[AgentEvent])
async def get_run_events(
    project_id: str,
    run_id: str,
    after_sequence: int = Query(default=0, ge=0),
    database: Database = Depends(get_database),
) -> list[AgentEvent]:
    run = RunRepository(database).get(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunRepository(database).list_events(run_id, after_sequence=after_sequence)


@router.get("/{run_id}/stream", response_class=StreamingResponse)
async def stream_run_events(project_id: str, run_id: str, database: Database = Depends(get_database)) -> StreamingResponse:
    repository = RunRepository(database)
    if repository.get(project_id, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def stream():
        sequence = 0
        while True:
            events = repository.list_events(run_id, after_sequence=sequence)
            for event in events:
                sequence = event.sequence
                yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
            run = repository.get(project_id, run_id)
            if run and run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELED} and not events:
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
