from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.assets import router as assets_router
from app.api.graph import router as graph_router
from app.api.projects import router as projects_router
from app.api.publication import router as publication_router
from app.api.runs import router as runs_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first Knowledge Graph Builder API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(health_router)
app.include_router(projects_router, prefix=settings.api_prefix)
app.include_router(runs_router, prefix=settings.api_prefix)
app.include_router(assets_router, prefix=settings.api_prefix)
app.include_router(publication_router, prefix=settings.api_prefix)
app.include_router(graph_router, prefix=settings.api_prefix)


@app.get("/", tags=["service"])
async def service_info() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
    }
