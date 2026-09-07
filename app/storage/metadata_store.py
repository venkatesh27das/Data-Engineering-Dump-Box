import sqlite3
from pathlib import Path

from app.models.run import Run, now
from app.models.workbook import Workbook


class MetadataStore:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS workbooks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS run_events (run_id TEXT, stage TEXT, created_at TEXT)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def save_workbook(self, workbook: Workbook) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO workbooks VALUES (?, ?)",
                (workbook.workbook_id, workbook.model_dump_json()),
            )

    def save_run(self, run: Run) -> None:
        run.updated_at = now()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?)", (run.run_id, run.model_dump_json()))
            db.execute(
                "INSERT INTO run_events VALUES (?, ?, ?)", (run.run_id, run.stage, run.updated_at.isoformat())
            )

    def workbook(self, identifier: str) -> Workbook:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM workbooks WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return Workbook.model_validate_json(row[0])

    def run(self, identifier: str) -> Run:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM runs WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return Run.model_validate_json(row[0])
