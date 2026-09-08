import fcntl
import json
from contextlib import contextmanager
from threading import Lock
from typing import Any, BinaryIO
from uuid import uuid4

from app.config.settings import Settings
from app.models.run import Run, Stage
from app.models.workbook import Workbook
from app.pipeline.ingest import ingest
from app.pipeline.orchestrator import process
from app.storage.metadata_store import MetadataStore


class BusyError(RuntimeError):
    pass


class RunService:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.prepare()
        self.metadata = MetadataStore(settings.sqlite_path)
        self.lock = Lock()  # Single local writer for DuckDB; use one Uvicorn worker.

    def upload(self, stream: BinaryIO, filename: str) -> Workbook:
        workbook = ingest(stream, filename, self.settings)
        self.metadata.save_workbook(workbook)
        self.metadata.save_run(Run(run_id=workbook.run_id, workbook_id=workbook.workbook_id))
        return workbook

    @contextmanager
    def writer(self):
        if not self.lock.acquire(blocking=False):
            raise BusyError("Another workbook is processing; retry after it completes")
        lock_file = None
        try:
            lock_file = self.settings.duckdb_path.with_suffix(".lock").open("a")
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BusyError("Another workbook is processing; retry after it completes") from exc
            yield
        finally:
            if lock_file is not None:
                lock_file.close()
            self.lock.release()

    def process(self, workbook_id: str, on_stage=None) -> Run:
        with self.writer():
            workbook = self.metadata.workbook(workbook_id)
            run = self.metadata.run(workbook.run_id)
            if run.stage != Stage.UPLOADED:
                workbook.run_id = uuid4().hex
                run = Run(run_id=workbook.run_id, workbook_id=workbook_id)
                self.metadata.save_run(run)
                self.metadata.save_workbook(workbook)
            return process(workbook, run, self.settings, self.metadata, on_stage=on_stage)

    def reprocess(self, region_id: str, request, on_stage=None) -> Run:
        from app.pipeline.reprocess_region import reprocess_region
        from app.services.feedback_service import FeedbackService

        with self.writer():
            workbook_id, parent_id, _ = self.metadata.region_context(region_id)
            parent = self.metadata.run(parent_id)
            if parent.stage not in (Stage.COMPLETED, Stage.COMPLETED_WITH_WARNINGS):
                raise BusyError("Region has no completed parent run")
            if request.content or request.expected_region_type:
                FeedbackService(self.metadata).submit(region_id, request)
            workbook = self.metadata.workbook(workbook_id)
            run = Run(
                run_id=uuid4().hex,
                workbook_id=workbook_id,
                parent_run_id=parent_id,
                reprocessed_region_id=region_id,
            )
            self.metadata.save_run(run)
            return reprocess_region(
                workbook, run, parent, region_id, request, self.settings, self.metadata, on_stage
            )

    def artifact(self, workbook_id: str, relative: str, jsonl: bool = False) -> Any:
        workbook = self.metadata.workbook(workbook_id)
        run = self.metadata.run(workbook.run_id)
        if run.stage not in (Stage.COMPLETED, Stage.COMPLETED_WITH_WARNINGS):
            raise BusyError("Workbook has no completed results")
        # relative is selected by application code, never from a request path.
        path = self.settings.output_dir / run.run_id / relative
        content = path.read_text(encoding="utf-8")
        return [json.loads(line) for line in content.splitlines()] if jsonl else json.loads(content)

    def system_status(self) -> dict:
        from app.llm.lmstudio_client import LMStudioClient
        from app.tools.rendering_tools import libreoffice_path

        model = LMStudioClient(self.settings).health_check()
        return {
            "lm_studio": model,
            "libreoffice_available": libreoffice_path() is not None,
            "agent_configured": bool(self.settings.enable_agent and self.settings.llm_model),
            "vlm_configured": bool(self.settings.enable_vlm and self.settings.vlm_model),
            "embeddings_configured": bool(self.settings.enable_embeddings and self.settings.embedding_model),
        }

    def search(self, query: str, limit: int = 10, run_id: str | None = None) -> list[dict]:
        from app.llm.lmstudio_client import LMStudioClient, ModelUnavailable
        from app.storage.vector_store import VectorStore

        if not self.settings.enable_embeddings or not self.settings.embedding_model:
            raise ModelUnavailable("Configure and enable an embedding model before semantic search")
        if not query.strip() or len(query) > 2000 or not 1 <= limit <= 20:
            raise ValueError("Search requires a query of 1–2000 characters and limit of 1–20")
        if run_id:
            self.metadata.run(run_id)
        vector = LMStudioClient(self.settings).embedding([query])[0]
        return VectorStore(self.settings.lancedb_path).search(
            vector, self.settings.embedding_model, limit, run_id
        )

    def render_region(self, region_id: str) -> list:
        from pathlib import Path

        from app.tools.rendering_tools import RenderingService

        workbook_id, run_id, region = self.metadata.region_context(region_id)
        workbook = self.metadata.workbook(workbook_id)
        sheets = json.loads((self.settings.output_dir / run_id / "metadata/sheets.json").read_text())
        sheet_name = next(s["name"] for s in sheets if s["sheet_id"] == region.sheet_id)
        destination = self.settings.data_dir / "processed" / "renders" / uuid4().hex
        return RenderingService(self.settings).render_sheet(
            Path(workbook.file_path), destination, sheet_name, region.range
        )
