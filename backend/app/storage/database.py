import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, settings: Settings):
        self.path = settings.database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(SCHEMA)

    def recover_interrupted_runs(self) -> int:
        active = ("queued", "profiling", "planning", "extracting", "interpreting", "validating", "packaging")
        placeholders = ", ".join("?" for _ in active)
        with self.connect() as db:
            cursor = db.execute(
                f"""UPDATE runs SET status = 'failed', current_stage = 'failed', completed_at = ?,
                error_code = 'WORKER_INTERRUPTED',
                error_message = 'The local worker stopped before this run completed.'
                WHERE status IN ({placeholders})""",
                (now_iso(), *active),
            )
            return cursor.rowcount

    def execute(self, sql: str, values: tuple[Any, ...] = ()) -> None:
        with self.connect() as db:
            db.execute(sql, values)

    def one(self, sql: str, values: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(sql, values).fetchone()
        return dict(row) if row else None

    def all(self, sql: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(sql, values).fetchall()
        return [dict(row) for row in rows]

    def create_workbook(self, record: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_iso()
        fields = {**record, "created_at": timestamp, "updated_at": timestamp, "latest_status": "queued"}
        with self.connect() as db:
            db.execute(
                """INSERT INTO workbooks
                (id, original_filename, display_name, file_type, file_size_bytes, sha256, storage_uri,
                 purpose, description, created_at, updated_at, latest_status)
                VALUES (:id, :original_filename, :display_name, :file_type, :file_size_bytes, :sha256,
                        :storage_uri, :purpose, :description, :created_at, :updated_at, :latest_status)""",
                fields,
            )
        return self.get_workbook(record["id"])  # type: ignore[return-value]

    def get_workbook(self, workbook_id: str) -> dict[str, Any] | None:
        return self.one("SELECT * FROM workbooks WHERE id = ?", (workbook_id,))

    def list_workbooks(self, search: str = "") -> list[dict[str, Any]]:
        term = f"%{search.lower()}%"
        return self.all(
            """SELECT * FROM workbooks WHERE is_archived = 0
            AND (LOWER(display_name) LIKE ? OR LOWER(purpose) LIKE ?) ORDER BY updated_at DESC""",
            (term, term),
        )

    def create_run(self, record: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as db:
            db.execute(
                """INSERT INTO runs
                (id, workbook_id, parent_run_id, run_number, trigger_type, scope, status,
                 current_stage, progress_percent, started_at)
                VALUES (:id, :workbook_id, :parent_run_id, :run_number, :trigger_type, :scope,
                        'queued', 'queued', 0, :started_at)""",
                {**record, "started_at": now_iso()},
            )
            db.execute(
                "UPDATE workbooks SET latest_run_id = ?, latest_status = 'queued', "
                "updated_at = ? WHERE id = ?",
                (record["id"], now_iso(), record["workbook_id"]),
            )
        return self.get_run(record["id"])  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.one(RUN_SELECT + " WHERE r.id = ?", (run_id,))

    def list_runs(self, search: str = "", workbook_id: str = "") -> list[dict[str, Any]]:
        clauses = ["(LOWER(w.display_name) LIKE ? OR LOWER(r.id) LIKE ?)"]
        values: list[Any] = [f"%{search.lower()}%", f"%{search.lower()}%"]
        if workbook_id:
            clauses.append("r.workbook_id = ?")
            values.append(workbook_id)
        return self.all(
            RUN_SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY r.started_at DESC", tuple(values)
        )

    def update_run(self, run_id: str, **changes: Any) -> None:
        if not changes:
            return
        assignments = ", ".join(f"{key} = ?" for key in changes)
        self.execute(f"UPDATE runs SET {assignments} WHERE id = ?", (*changes.values(), run_id))
        run = self.get_run(run_id)
        if run:
            self.execute(
                """UPDATE workbooks SET latest_status = ?, latest_confidence = COALESCE(?, latest_confidence),
                updated_at = ? WHERE id = ? AND latest_run_id = ?""",
                (run["status"], run["overall_confidence"], now_iso(), run["workbook_id"], run_id),
            )

    def add_event(self, event: dict[str, Any]) -> None:
        self.execute(
            """INSERT INTO events
            (event_id, run_id, timestamp, stage, status, progress_percent, message, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event["event_id"],
                event["run_id"],
                event["timestamp"],
                event["stage"],
                event["status"],
                event["progress_percent"],
                event["message"],
                json.dumps(event.get("details", {})),
            ),
        )

    def list_events(self, run_id: str, after: str = "") -> list[dict[str, Any]]:
        rows = self.all(
            "SELECT * FROM events WHERE run_id = ? AND timestamp > ? ORDER BY timestamp", (run_id, after)
        )
        for row in rows:
            row["details"] = json.loads(row["details"])
        return rows

    def replace_assets(self, run_id: str, workbook_id: str, assets: list[dict[str, Any]]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM assets WHERE run_id = ?", (run_id,))
            db.executemany(
                """INSERT INTO assets (id, run_id, workbook_id, asset_type, title, summary, source_uri,
                content_uri, source_sheet, source_range, confidence, review_status, created_at)
                VALUES (:id, :run_id, :workbook_id, :asset_type, :title, :summary, :source_uri,
                :content_uri, :source_sheet, :source_range, :confidence, :review_status, :created_at)""",
                [
                    {
                        **asset,
                        "id": f"{run_id}:{asset['id']}",
                        "run_id": run_id,
                        "workbook_id": workbook_id,
                        "created_at": now_iso(),
                    }
                    for asset in assets
                ],
            )

    def list_assets(self, run_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM assets WHERE run_id = ? ORDER BY asset_type, title", (run_id,))

    def replace_reviews(self, run_id: str, items: list[dict[str, Any]]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM review_items WHERE run_id = ?", (run_id,))
            db.executemany(
                """INSERT INTO review_items (id, run_id, asset_id, review_type, title, description,
                evidence, suggested_action, confidence, severity, status)
                VALUES (:id, :run_id, :asset_id, :review_type, :title, :description, :evidence,
                :suggested_action, :confidence, :severity, 'open')""",
                [{**item, "run_id": run_id} for item in items],
            )

    def list_reviews(self, run_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM review_items WHERE run_id = ? ORDER BY confidence", (run_id,))

    def resolve_review(self, item_id: str, status: str, resolution: str = "") -> dict[str, Any] | None:
        self.execute(
            "UPDATE review_items SET status = ?, resolution = ?, resolved_at = ? WHERE id = ?",
            (status, resolution, now_iso(), item_id),
        )
        return self.one("SELECT * FROM review_items WHERE id = ?", (item_id,))

    def save_feedback(self, record: dict[str, Any]) -> None:
        self.execute(
            """INSERT INTO feedback (id, run_id, workbook_id, raw_text, scope_type, parsed_directives,
            parse_confidence, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'applied', ?)""",
            (
                record["id"],
                record["run_id"],
                record["workbook_id"],
                record["raw_text"],
                record["scope_type"],
                json.dumps(record["parsed_directives"]),
                record["parse_confidence"],
                now_iso(),
            ),
        )


RUN_SELECT = """SELECT r.*, w.display_name AS workbook_name, w.purpose AS purpose
FROM runs r JOIN workbooks w ON w.id = r.workbook_id"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS workbooks (
 id TEXT PRIMARY KEY, original_filename TEXT NOT NULL, display_name TEXT NOT NULL, file_type TEXT NOT NULL,
 file_size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, storage_uri TEXT NOT NULL, purpose TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 latest_run_id TEXT, latest_status TEXT NOT NULL DEFAULT 'queued', latest_confidence REAL,
 is_archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, workbook_id TEXT NOT NULL REFERENCES workbooks(id), parent_run_id TEXT,
 run_number INTEGER NOT NULL, trigger_type TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL,
 current_stage TEXT NOT NULL, progress_percent INTEGER NOT NULL DEFAULT 0, started_at TEXT,
 completed_at TEXT, duration_seconds REAL, overall_confidence REAL, output_unit_count INTEGER,
 error_code TEXT, error_message TEXT, accepted_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
 event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), timestamp TEXT NOT NULL,
 stage TEXT NOT NULL, status TEXT NOT NULL, progress_percent INTEGER NOT NULL, message TEXT NOT NULL,
 details TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 workbook_id TEXT NOT NULL REFERENCES workbooks(id),
 asset_type TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL, source_uri TEXT NOT NULL,
 content_uri TEXT NOT NULL, source_sheet TEXT, source_range TEXT, confidence REAL NOT NULL,
 review_status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_items (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), asset_id TEXT, review_type TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, evidence TEXT NOT NULL, suggested_action TEXT NOT NULL,
 confidence REAL NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL, resolution TEXT,
 resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL, workbook_id TEXT NOT NULL, raw_text TEXT NOT NULL,
 scope_type TEXT NOT NULL, parsed_directives TEXT NOT NULL, parse_confidence REAL NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_workbook ON runs(workbook_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_assets_run ON assets(run_id);
"""
