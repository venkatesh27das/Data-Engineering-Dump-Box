import json
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

    def process(self, workbook_id: str) -> Run:
        if not self.lock.acquire(blocking=False):
            raise BusyError("Another workbook is processing; retry after it completes")
        try:
            workbook = self.metadata.workbook(workbook_id)
            run = self.metadata.run(workbook.run_id)
            if run.stage != Stage.UPLOADED:
                workbook.run_id = uuid4().hex
                run = Run(run_id=workbook.run_id, workbook_id=workbook_id)
                self.metadata.save_run(run)
                self.metadata.save_workbook(workbook)
            return process(workbook, run, self.settings, self.metadata)
        finally:
            self.lock.release()

    def artifact(self, workbook_id: str, relative: str, jsonl: bool = False) -> Any:
        workbook = self.metadata.workbook(workbook_id)
        run = self.metadata.run(workbook.run_id)
        if run.stage not in (Stage.COMPLETED, Stage.COMPLETED_WITH_WARNINGS):
            raise BusyError("Workbook has no completed results")
        # relative is selected by application code, never from a request path.
        path = self.settings.output_dir / run.run_id / relative
        content = path.read_text(encoding="utf-8")
        return [json.loads(line) for line in content.splitlines()] if jsonl else json.loads(content)
