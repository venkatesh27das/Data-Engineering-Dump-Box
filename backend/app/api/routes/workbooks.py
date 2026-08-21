from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_database, get_intake, get_processor
from app.domain.schemas import RunOut, WorkbookOut
from app.services.intake_service import IntakeService
from app.services.run_processor import RunProcessor
from app.storage.database import Database, now_iso

router = APIRouter(prefix="/workbooks", tags=["workbooks"])


@router.post("")
def upload_workbook(
    file: UploadFile = File(...),
    purpose: str = Form("Knowledge extraction / Entity & relationship"),
    description: str = Form(""),
    intake: IntakeService = Depends(get_intake),
    processor: RunProcessor = Depends(get_processor),
) -> dict[str, Any]:
    workbook, run = intake.upload(file, purpose, description)
    processor.submit(run["id"])
    return {"workbook": WorkbookOut.model_validate(workbook), "run": RunOut.model_validate(run)}


@router.get("", response_model=list[WorkbookOut])
def list_workbooks(search: str = "", database: Database = Depends(get_database)) -> list[dict]:
    return database.list_workbooks(search)


@router.get("/{workbook_id}", response_model=WorkbookOut)
def get_workbook(workbook_id: str, database: Database = Depends(get_database)) -> dict:
    workbook = database.get_workbook(workbook_id)
    if not workbook:
        raise HTTPException(404, "Workbook not found")
    return workbook


@router.patch("/{workbook_id}", response_model=WorkbookOut)
def update_workbook(
    workbook_id: str, payload: dict[str, Any], database: Database = Depends(get_database)
) -> dict:
    allowed = {key: payload[key] for key in ("display_name", "description", "is_archived") if key in payload}
    if allowed:
        allowed["updated_at"] = now_iso()
        assignments = ", ".join(f"{key} = ?" for key in allowed)
        database.execute(f"UPDATE workbooks SET {assignments} WHERE id = ?", (*allowed.values(), workbook_id))
    workbook = database.get_workbook(workbook_id)
    if not workbook:
        raise HTTPException(404, "Workbook not found")
    return workbook


@router.delete("/{workbook_id}", response_model=WorkbookOut)
def archive_workbook(workbook_id: str, database: Database = Depends(get_database)) -> dict:
    database.execute(
        "UPDATE workbooks SET is_archived = 1, updated_at = ? WHERE id = ?", (now_iso(), workbook_id)
    )
    workbook = database.get_workbook(workbook_id)
    if not workbook:
        raise HTTPException(404, "Workbook not found")
    return workbook


@router.post("/{workbook_id}/runs", response_model=RunOut)
def start_run(
    workbook_id: str,
    intake: IntakeService = Depends(get_intake),
    processor: RunProcessor = Depends(get_processor),
    database: Database = Depends(get_database),
) -> dict:
    if not database.get_workbook(workbook_id):
        raise HTTPException(404, "Workbook not found")
    run = intake.create_run(workbook_id, trigger_type="manual_rerun")
    processor.submit(run["id"])
    return run
