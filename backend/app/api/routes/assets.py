from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import get_database
from app.domain.schemas import AssetOut
from app.storage.database import Database

router = APIRouter(tags=["assets"])


@router.get("/runs/{run_id}/assets", response_model=list[AssetOut])
def list_assets(run_id: str, database: Database = Depends(get_database)) -> list[dict]:
    if not database.get_run(run_id):
        raise HTTPException(404, "Run not found")
    return database.list_assets(run_id)


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, database: Database = Depends(get_database)) -> dict:
    asset = database.one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


@router.get("/assets/{asset_id}/download")
def download_asset(asset_id: str, database: Database = Depends(get_database)) -> FileResponse:
    asset = database.one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(404, "Asset not found")
    path = Path(asset["content_uri"])
    if not path.is_file():
        raise HTTPException(404, "Asset content is unavailable")
    return FileResponse(path)
