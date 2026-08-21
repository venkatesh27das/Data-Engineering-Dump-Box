from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.deepagents_runtime import DeepAgentsRuntime
from app.api.routes import assets, health, models, reviews, runs, workbooks
from app.core.config import get_settings
from app.core.errors import WorkbookError
from app.llm.lmstudio_client import LMStudioClient
from app.llm.model_registry import ModelRegistry
from app.services.intake_service import IntakeService
from app.services.run_processor import RunProcessor
from app.storage.database import Database
from app.storage.local_store import LocalStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database = Database(settings)
    database.initialize()
    database.recover_interrupted_runs()
    store = LocalStore(settings)
    models_registry = ModelRegistry(settings)
    lmstudio_client = LMStudioClient(settings)
    agent_runtime = DeepAgentsRuntime(settings, models_registry, lmstudio_client)
    app.state.settings = settings
    app.state.database = database
    app.state.store = store
    app.state.models = models_registry
    app.state.agent_runtime = agent_runtime
    app.state.intake = IntakeService(settings, database, store)
    app.state.processor = RunProcessor(database, store, models_registry, agent_runtime)
    yield
    app.state.processor.executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Workbook Agent API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (health.router, models.router, workbooks.router, runs.router, assets.router, reviews.router):
    app.include_router(router, prefix="/api/v1")


@app.exception_handler(WorkbookError)
async def workbook_error_handler(_: Request, error: WorkbookError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code, content={"detail": {"code": error.code, "message": error.message}}
    )
