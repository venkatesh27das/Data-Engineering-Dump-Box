import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config.settings import Settings
from app.pipeline.ingest import InvalidWorkbook
from app.services.run_service import BusyError, RunService


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
    @asynccontextmanager
    async def lifespan(api):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("app")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        api.state.service = RunService(settings or Settings())
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
        return {"status": "ok", "phase": 1, "agents_enabled": False}

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

    return api


app = create_app()
