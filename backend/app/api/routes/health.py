from fastapi import APIRouter, Depends

from app.api.dependencies import get_database
from app.storage.database import Database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(database: Database = Depends(get_database)) -> dict:
    database.one("SELECT 1 AS ok")
    return {"status": "ok", "service": "workbook-agent", "version": "0.1.0"}
