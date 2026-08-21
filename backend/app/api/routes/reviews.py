from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_database
from app.domain.schemas import ReviewItemOut
from app.storage.database import Database

router = APIRouter(tags=["review"])


@router.get("/runs/{run_id}/review-items", response_model=list[ReviewItemOut])
def list_review_items(run_id: str, database: Database = Depends(get_database)) -> list[dict]:
    return database.list_reviews(run_id)


def _resolve(item_id: str, status: str, database: Database) -> dict:
    item = database.resolve_review(item_id, status)
    if not item:
        raise HTTPException(404, "Review item not found")
    return item


@router.post("/review-items/{item_id}/confirm", response_model=ReviewItemOut)
def confirm(item_id: str, database: Database = Depends(get_database)) -> dict:
    return _resolve(item_id, "confirmed", database)


@router.post("/review-items/{item_id}/correct", response_model=ReviewItemOut)
def correct(item_id: str, database: Database = Depends(get_database)) -> dict:
    return _resolve(item_id, "corrected", database)


@router.post("/review-items/{item_id}/reject", response_model=ReviewItemOut)
def reject(item_id: str, database: Database = Depends(get_database)) -> dict:
    return _resolve(item_id, "rejected", database)


@router.post("/review-items/{item_id}/ignore", response_model=ReviewItemOut)
def ignore(item_id: str, database: Database = Depends(get_database)) -> dict:
    return _resolve(item_id, "ignored", database)
