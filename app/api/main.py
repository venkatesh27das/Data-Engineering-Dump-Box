import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config.settings import Settings
from app.llm.lmstudio_client import ModelUnavailable
from app.pipeline.ingest import InvalidWorkbook
from app.services.feedback_service import FeedbackRequest, FeedbackService, ReprocessRequest, SearchRequest
from app.services.run_service import BusyError, RunService
from app.tools.rendering_tools import RenderingUnavailable


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname, "message": record.getMessage()}
        for key in ("run_id", "workbook_id", "sheet_name", "region_id", "stage"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(api):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("app")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        api.state.service = RunService(configured_settings)
        yield
        logger.removeHandler(handler)

    api = FastAPI(title="Excel Intelligence", version="0.1.0", lifespan=lifespan)

    @api.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Workbook or run not found"})

    @api.exception_handler(InvalidWorkbook)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @api.exception_handler(BusyError)
    async def busy(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @api.get("/health")
    def health():
        return {
            "status": "ok",
            "phase": 5,
            "agents_enabled": bool(configured_settings.enable_agent and configured_settings.llm_model),
        }

    @api.post("/workbooks/upload", status_code=201)
    def upload(request: Request, file: Annotated[UploadFile, File()]):
        try:
            return request.app.state.service.upload(file.file, file.filename or "")
        finally:
            file.file.close()

    @api.post("/workbooks/{workbook_id}/process")
    def process(workbook_id: str, request: Request):
        return request.app.state.service.process(workbook_id)

    @api.get("/runs/{run_id}")
    @api.get("/runs/{run_id}/status")
    def run(run_id: str, request: Request):
        return request.app.state.service.metadata.run(run_id)

    @api.get("/workbooks/{workbook_id}")
    def workbook(workbook_id: str, request: Request):
        return request.app.state.service.metadata.workbook(workbook_id)

    @api.get("/workbooks/{workbook_id}/sheets")
    def sheets(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/sheets.json")

    @api.get("/workbooks/{workbook_id}/tables")
    def tables(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/table_assets.json")

    @api.get("/workbooks/{workbook_id}/formulas")
    def formulas(workbook_id: str, request: Request, offset: int = 0, limit: int = 100):
        from fastapi import HTTPException

        if offset < 0 or not 1 <= limit <= 1000:
            raise HTTPException(422, "offset >= 0 and 1 <= limit <= 1000 required")
        return request.app.state.service.artifact(workbook_id, "formulas/formulas.jsonl", True)[
            offset : offset + limit
        ]

    @api.get("/workbooks/{workbook_id}/graph")
    def graph(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "graph/dependency_graph.json")

    @api.get("/workbooks/{workbook_id}/regions")
    def regions(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/regions.json")

    @api.get("/regions/{region_id}")
    def region(region_id: str, request: Request):
        service = request.app.state.service
        workbook_id, run_id, asset = service.metadata.region_context(region_id)
        return {
            "workbook_id": workbook_id,
            "run_id": run_id,
            "region": asset,
            "feedback": service.metadata.feedback(region_id),
        }

    @api.post("/regions/{region_id}/feedback", status_code=201)
    def feedback(region_id: str, body: FeedbackRequest, request: Request):
        return FeedbackService(request.app.state.service.metadata).submit(region_id, body)

    @api.post("/regions/{region_id}/reprocess")
    def reprocess(region_id: str, body: ReprocessRequest, request: Request):
        return request.app.state.service.reprocess(region_id, body)

    @api.exception_handler(ModelUnavailable)
    @api.exception_handler(RenderingUnavailable)
    async def enrichment_unavailable(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @api.exception_handler(ValueError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @api.get("/system/status")
    def system_status(request: Request):
        return request.app.state.service.system_status()

    @api.get("/workbooks/{workbook_id}/text")
    def text_assets(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "text/text_assets.jsonl", True)

    @api.get("/workbooks/{workbook_id}/images")
    def images(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/images.json")

    @api.get("/workbooks/{workbook_id}/charts")
    def charts(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/charts.json")

    @api.get("/workbooks/{workbook_id}/summaries")
    def summaries(workbook_id: str, request: Request):
        return request.app.state.service.artifact(workbook_id, "metadata/summaries.json")

    @api.post("/regions/{region_id}/render")
    def render(region_id: str, request: Request):
        return {"pages": [str(p) for p in request.app.state.service.render_region(region_id)]}

    @api.post("/search")
    def search(body: SearchRequest, request: Request):
        return request.app.state.service.search(body.query, body.limit, body.run_id)

    return api


app = create_app()
