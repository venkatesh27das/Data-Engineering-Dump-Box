import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from app.api.dependencies import get_database, get_store
from app.domain.schemas import AssetOut
from app.services.run_inspection_service import (
    get_asset_content,
    package_root,
    resolve_package_file,
)
from app.storage.database import Database
from app.storage.local_store import LocalStore

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


@router.get("/assets/{asset_id}/content")
def view_asset_content(
    asset_id: str,
    database: Database = Depends(get_database),
    store: LocalStore = Depends(get_store),
) -> dict:
    asset = database.one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(404, "Asset not found")
    return get_asset_content(asset, store)


@router.get("/assets/{asset_id}/preview")
def preview_asset(
    asset_id: str,
    database: Database = Depends(get_database),
    store: LocalStore = Depends(get_store),
) -> FileResponse:
    asset = database.one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(404, "Asset not found")
    content = get_asset_content(asset, store)
    preview = resolve_package_file(package_root(store, asset), content["preview_file"])
    if not preview:
        raise HTTPException(409, "This asset does not have a visual preview")
    return FileResponse(preview)


@router.get("/assets/{asset_id}/download")
def download_asset(
    asset_id: str,
    database: Database = Depends(get_database),
    store: LocalStore = Depends(get_store),
) -> Response:
    asset = database.one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not asset:
        raise HTTPException(404, "Asset not found")
    content = get_asset_content(asset, store)
    root = package_root(store, asset)
    specific_file = resolve_package_file(
        root, content["preview_file"] or content["data_file"]
    )
    if specific_file:
        return FileResponse(specific_file, filename=specific_file.name)
    record = content.get("record")
    if record is not None:
        safe_name = LocalStore.sanitize_filename(asset["title"]).removesuffix(".xlsx")
        return Response(
            json.dumps(record, indent=2, ensure_ascii=False, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.json"'},
        )
    path = Path(asset["content_uri"])
    if path.is_file():
        return FileResponse(path)
    raise HTTPException(404, "Asset content is unavailable")
