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

    def save_regions(self, workbook_id: str, run_id: str, regions) -> None:
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS region_index (id TEXT PRIMARY KEY, workbook_id TEXT, run_id TEXT, payload TEXT)"
            )
            db.executemany(
                "INSERT OR REPLACE INTO region_index VALUES (?, ?, ?, ?)",
                [(r.region_id, workbook_id, run_id, r.model_dump_json()) for r in regions],
            )

    def region_context(self, identifier: str):
        from app.models.region import Region

        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS region_index (id TEXT PRIMARY KEY, workbook_id TEXT, run_id TEXT, payload TEXT)"
            )
            row = db.execute(
                "SELECT workbook_id, run_id, payload FROM region_index WHERE id=?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return row[0], row[1], Region.model_validate_json(row[2])

    def save_feedback(self, feedback) -> None:
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, region_id TEXT, payload TEXT)"
            )
            db.execute(
                "INSERT INTO feedback VALUES (?, ?, ?)",
                (feedback.feedback_id, feedback.region_id, feedback.model_dump_json()),
            )

    def feedback(self, region_id: str) -> list:
        from app.models.assets import Feedback

        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, region_id TEXT, payload TEXT)"
            )
            rows = db.execute(
                "SELECT payload FROM feedback WHERE region_id=? ORDER BY rowid", (region_id,)
            ).fetchall()
        return [Feedback.model_validate_json(row[0]) for row in rows]
