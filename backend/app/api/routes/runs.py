import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.agents.runtime import AgentRuntime
from app.api.dependencies import (
    get_agent_runtime,
    get_database,
    get_intake,
    get_processor,
    get_store,
)
from app.domain.schemas import FeedbackRequest, RunOut
from app.services.feedback_service import parse_feedback
from app.services.intake_service import IntakeService
from app.services.run_processor import RunProcessor
from app.storage.database import Database, now_iso
from app.storage.local_store import LocalStore

router = APIRouter(prefix="/runs", tags=["runs"])
TERMINAL = {"completed", "needs_review", "failed", "cancelled"}


@router.get("", response_model=list[RunOut])
def list_runs(
    search: str = "", workbook_id: str = "", database: Database = Depends(get_database)
) -> list[dict]:
    return database.list_runs(search, workbook_id)


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, database: Database = Depends(get_database)) -> dict:
    run = database.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/{run_id}/events")
def run_events(run_id: str, database: Database = Depends(get_database)) -> StreamingResponse:
    if not database.get_run(run_id):
        raise HTTPException(404, "Run not found")

    async def stream():
        after = ""
        while True:
            events = database.list_events(run_id, after)
            for event in events:
                after = max(after, event["timestamp"])
                yield f"id: {event['event_id']}\ndata: {json.dumps(event, default=str)}\n\n"
            run = database.get_run(run_id)
            if run and run["status"] in TERMINAL and not events:
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.7)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/cancel", response_model=RunOut)
def cancel_run(
    run_id: str, processor: RunProcessor = Depends(get_processor), database: Database = Depends(get_database)
) -> dict:
    run = database.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    processor.cancel(run_id)
    return run


@router.post("/{run_id}/retry", response_model=RunOut)
def retry_run(
    run_id: str,
    intake: IntakeService = Depends(get_intake),
    processor: RunProcessor = Depends(get_processor),
    database: Database = Depends(get_database),
) -> dict:
    parent = database.get_run(run_id)
    if not parent:
        raise HTTPException(404, "Run not found")
    child = intake.create_run(parent["workbook_id"], run_id, "retry", "full_workbook")
    processor.submit(child["id"])
    return child


@router.post("/{run_id}/accept", response_model=RunOut)
def accept_run(run_id: str, database: Database = Depends(get_database)) -> dict:
    run = database.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] not in {"completed", "needs_review"}:
        raise HTTPException(409, "Only completed runs can be accepted")
    database.execute("UPDATE runs SET accepted_at = ? WHERE id = ?", (now_iso(), run_id))
    database.execute(
        "UPDATE workbooks SET latest_run_id = ?, latest_status = ?, "
        "latest_confidence = ?, updated_at = ? WHERE id = ?",
        (run_id, run["status"], run["overall_confidence"], now_iso(), run["workbook_id"]),
    )
    return database.get_run(run_id)


@router.get("/{run_id}/compare/{other_run_id}")
def compare_runs(
    run_id: str, other_run_id: str, database: Database = Depends(get_database)
) -> dict[str, Any]:
    current, previous = database.get_run(run_id), database.get_run(other_run_id)
    if not current or not previous:
        raise HTTPException(404, "Run not found")
    current_assets = database.list_assets(run_id)
    previous_assets = database.list_assets(other_run_id)
    current_keys = {(item["asset_type"], item["title"]) for item in current_assets}
    previous_keys = {(item["asset_type"], item["title"]) for item in previous_assets}
    return {
        "current_run_id": run_id,
        "other_run_id": other_run_id,
        "assets_added": len(current_keys - previous_keys),
        "assets_removed": len(previous_keys - current_keys),
        "asset_count_change": len(current_assets) - len(previous_assets),
        "confidence_change": (current["overall_confidence"] or 0) - (previous["overall_confidence"] or 0),
        "review_item_change": len(database.list_reviews(run_id)) - len(database.list_reviews(other_run_id)),
    }


@router.post("/{run_id}/feedback/parse")
def preview_feedback(
    run_id: str,
    payload: FeedbackRequest,
    database: Database = Depends(get_database),
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict[str, Any]:
    if not database.get_run(run_id):
        raise HTTPException(404, "Run not found")
    directives = parse_feedback(payload.raw_text, runtime)
    return {
        "directives": directives,
        "requires_confirmation": any(item["requires_confirmation"] for item in directives),
    }


@router.post("/{run_id}/reprocess", response_model=RunOut)
def reprocess_run(
    payload: FeedbackRequest,
    run_id: str,
    intake: IntakeService = Depends(get_intake),
    processor: RunProcessor = Depends(get_processor),
    database: Database = Depends(get_database),
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict:
    parent = database.get_run(run_id)
    if not parent:
        raise HTTPException(404, "Run not found")
    directives = parse_feedback(payload.raw_text, runtime)
    child = intake.create_run(parent["workbook_id"], run_id, "feedback_rerun", payload.scope)
    database.save_feedback(
        {
            "id": f"feedback_{child['id']}",
            "run_id": child["id"],
            "workbook_id": parent["workbook_id"],
            "raw_text": payload.raw_text,
            "scope_type": payload.scope,
            "parsed_directives": directives,
            "parse_confidence": sum(item["confidence"] for item in directives) / len(directives),
        }
    )
    processor.submit(child["id"], directives)
    return child


@router.get("/{run_id}/directives")
def get_directives(run_id: str, database: Database = Depends(get_database)) -> list[dict[str, Any]]:
    rows = database.all("SELECT parsed_directives FROM feedback WHERE run_id = ?", (run_id,))
    return [directive for row in rows for directive in json.loads(row["parsed_directives"])]


@router.get("/{run_id}/package/download")
def download_package(
    run_id: str, database: Database = Depends(get_database), store: LocalStore = Depends(get_store)
) -> FileResponse:
    run = database.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    path = store.run_path(run["workbook_id"], run_id) / "workbook_knowledge_package.zip"
    if not path.is_file():
        raise HTTPException(409, "The package is not ready yet")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{Path(run['workbook_name']).stem}-knowledge-package.zip",
    )
