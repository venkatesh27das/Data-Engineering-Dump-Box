from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.domain.assets import ReviewStatus
from app.domain.review import (
    AssetKind,
    AssetOverview,
    AssetPage,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from app.repositories.projects import ProjectRepository
from app.repositories.runs import AssetPackageRepository
from app.services.assets import AssetNotFoundError, AssetService
from app.storage.database import Database, get_database

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


def _repository(database: Database, settings: Settings) -> AssetPackageRepository:
    return AssetPackageRepository(database, settings.artifact_path)


def _require_project_and_package(project_id: str, database: Database, settings: Settings):
    if ProjectRepository(database).get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    package = _repository(database, settings).load_latest(project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="No generated asset package found")
    return package


@router.get("", response_model=AssetOverview)
async def get_asset_overview(
    project_id: str,
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AssetOverview:
    package = _require_project_and_package(project_id, database, settings)
    summary = _repository(database, settings).latest_summary(project_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="No generated asset package found")
    return AssetOverview(package=summary, quality=package.quality_report)


async def _list_assets(
    kind: AssetKind,
    project_id: str,
    database: Database,
    settings: Settings,
    search: str | None,
    asset_type: str | None,
    source: str | None,
    minimum_confidence: float | None,
    maximum_confidence: float | None,
    review_status: ReviewStatus | None,
    page: int,
    page_size: int,
) -> AssetPage:
    package = _require_project_and_package(project_id, database, settings)
    return AssetService.page(package, kind, search=search, asset_type=asset_type, source=source, minimum_confidence=minimum_confidence, maximum_confidence=maximum_confidence, review_status=review_status, page=page, page_size=page_size)


def _register_list_route(kind: AssetKind) -> None:
    async def endpoint(
        project_id: str,
        search: str | None = Query(default=None, max_length=200),
        asset_type: str | None = Query(default=None, max_length=100),
        source: str | None = Query(default=None, max_length=255),
        minimum_confidence: float | None = Query(default=None, ge=0, le=1),
        maximum_confidence: float | None = Query(default=None, ge=0, le=1),
        review_status: ReviewStatus | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=100),
        database: Database = Depends(get_database),
        settings: Settings = Depends(get_settings),
    ) -> AssetPage:
        return await _list_assets(kind, project_id, database, settings, search, asset_type, source, minimum_confidence, maximum_confidence, review_status, page, page_size)

    endpoint.__name__ = f"list_{kind.value}"
    router.add_api_route(f"/{kind.value}", endpoint, methods=["GET"], response_model=AssetPage)


for asset_kind in AssetKind:
    _register_list_route(asset_kind)


async def _review(
    project_id: str,
    asset_id: str,
    decision: ReviewStatus,
    payload: ReviewDecisionRequest,
    database: Database,
    settings: Settings,
) -> ReviewDecisionResponse:
    package = _require_project_and_package(project_id, database, settings)
    repository = _repository(database, settings)
    try:
        updated_package, view = AssetService.set_review_status(package, asset_id, decision)
    except AssetNotFoundError as error:
        raise HTTPException(status_code=404, detail="Asset not found") from error
    repository.replace(updated_package)
    repository.record_review(project_id, package.package_id, asset_id, decision.value, payload.note)
    return ReviewDecisionResponse(asset=view, decision=decision)


@router.post("/{asset_id}/approve", response_model=ReviewDecisionResponse)
async def approve_asset(project_id: str, asset_id: str, payload: ReviewDecisionRequest, database: Database = Depends(get_database), settings: Settings = Depends(get_settings)) -> ReviewDecisionResponse:
    return await _review(project_id, asset_id, ReviewStatus.APPROVED, payload, database, settings)


@router.post("/{asset_id}/review", response_model=ReviewDecisionResponse)
async def mark_asset_for_review(project_id: str, asset_id: str, payload: ReviewDecisionRequest, database: Database = Depends(get_database), settings: Settings = Depends(get_settings)) -> ReviewDecisionResponse:
    return await _review(project_id, asset_id, ReviewStatus.REVIEW, payload, database, settings)


@router.post("/{asset_id}/reject", response_model=ReviewDecisionResponse)
async def reject_asset(project_id: str, asset_id: str, payload: ReviewDecisionRequest, database: Database = Depends(get_database), settings: Settings = Depends(get_settings)) -> ReviewDecisionResponse:
    return await _review(project_id, asset_id, ReviewStatus.REJECTED, payload, database, settings)
