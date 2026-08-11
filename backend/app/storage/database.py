import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends

from app.config import Settings, get_settings


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialized = False
        self._lock = threading.Lock()

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect(initialize=False) as connection:
                connection.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    PRAGMA foreign_keys=ON;

                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        knowledge_objective TEXT NOT NULL,
                        processing_mode TEXT NOT NULL,
                        graph_depth TEXT NOT NULL,
                        review_low_confidence INTEGER NOT NULL,
                        max_tokens INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS sources (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        filename TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        category TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        mime_type TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        storage_path TEXT NOT NULL,
                        status TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_sources_project_id
                    ON sources(project_id);

                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        status TEXT NOT NULL,
                        current_stage TEXT NOT NULL,
                        plan_json TEXT,
                        package_id TEXT,
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT
                    );

                    CREATE TABLE IF NOT EXISTS agent_events (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                        sequence INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        status TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        UNIQUE(run_id, sequence)
                    );

                    CREATE INDEX IF NOT EXISTS idx_agent_events_run
                    ON agent_events(run_id, sequence);

                    CREATE TABLE IF NOT EXISTS run_artifacts (
                        id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                        stage TEXT NOT NULL,
                        artifact_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        record_count INTEGER NOT NULL DEFAULT 0,
                        parent_ids_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_run_artifacts_run
                    ON run_artifacts(run_id, created_at);

                    CREATE TABLE IF NOT EXISTS asset_packages (
                        package_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                        artifact_path TEXT NOT NULL,
                        entity_count INTEGER NOT NULL,
                        relationship_count INTEGER NOT NULL,
                        concept_count INTEGER NOT NULL,
                        fact_count INTEGER NOT NULL,
                        event_count INTEGER NOT NULL,
                        quality_score REAL NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_asset_packages_project
                    ON asset_packages(project_id, created_at DESC);

                    CREATE TABLE IF NOT EXISTS review_decisions (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        package_id TEXT NOT NULL REFERENCES asset_packages(package_id) ON DELETE CASCADE,
                        asset_id TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        note TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS publications (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        package_id TEXT NOT NULL REFERENCES asset_packages(package_id) ON DELETE CASCADE,
                        status TEXT NOT NULL,
                        nodes_published INTEGER NOT NULL DEFAULT 0,
                        relationships_published INTEGER NOT NULL DEFAULT 0,
                        assets_skipped INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        completed_at TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_publications_project
                    ON publications(project_id, created_at DESC);
                    """
                )
            self._initialized = True

    @contextmanager
    def connect(self, *, initialize: bool = True) -> Iterator[sqlite3.Connection]:
        if initialize:
            self.initialize()
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


_databases: dict[Path, Database] = {}
_databases_lock = threading.Lock()


def get_database(settings: Settings = Depends(get_settings)) -> Database:
    path = settings.sqlite_path
    with _databases_lock:
        if path not in _databases:
            _databases[path] = Database(path)
        return _databases[path]
