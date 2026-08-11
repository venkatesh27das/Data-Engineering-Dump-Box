import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.assets import KnowledgeAssetPackage
from app.domain.runs import AgentEvent, AssetPackageSummary, ExecutionPlan, Run, RunArtifact, RunQueueItem, RunStatus
from app.storage.database import Database


class RunRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, project_id: str) -> Run:
        run = Run(id=str(uuid4()), project_id=project_id, status=RunStatus.QUEUED, current_stage="queued", created_at=datetime.now(UTC))
        with self.database.connect() as connection:
            connection.execute("INSERT INTO runs (id, project_id, status, current_stage, created_at) VALUES (?, ?, ?, ?, ?)", (run.id, run.project_id, run.status.value, run.current_stage, run.created_at.isoformat()))
        return run

    def get(self, project_id: str, run_id: str) -> Run | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE project_id = ? AND id = ?", (project_id, run_id)).fetchone()
        return self._from_row(row) if row else None

    def get_by_id(self, run_id: str) -> Run | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_active(self) -> list[Run]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs WHERE status IN (?, ?) ORDER BY created_at",
                (RunStatus.QUEUED.value, RunStatus.RUNNING.value),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_queue(
        self,
        *,
        status: RunStatus | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[RunQueueItem]:
        where: list[str] = []
        parameters: list[object] = []
        if status is not None:
            where.append("r.status = ?")
            parameters.append(status.value)
        if project_id is not None:
            where.append("r.project_id = ?")
            parameters.append(project_id)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        parameters.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT r.*, p.name AS project_name,
                    (SELECT COUNT(*) FROM sources s WHERE s.project_id = r.project_id) AS source_count,
                    (SELECT COUNT(*) FROM agent_events e WHERE e.run_id = r.id) AS event_count,
                    (SELECT COUNT(*) FROM run_artifacts ra WHERE ra.run_id = r.id) AS artifact_count,
                    ap.package_id AS summary_package_id, ap.entity_count, ap.relationship_count,
                    ap.concept_count, ap.fact_count, ap.event_count AS package_event_count,
                    ap.quality_score, ap.created_at AS package_created_at
                FROM runs r
                JOIN projects p ON p.id = r.project_id
                LEFT JOIN asset_packages ap ON ap.run_id = r.id
                {clause}
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        items: list[RunQueueItem] = []
        for row in rows:
            package = None
            if row["summary_package_id"]:
                package = AssetPackageSummary(
                    package_id=row["summary_package_id"],
                    project_id=row["project_id"],
                    run_id=row["id"],
                    entity_count=row["entity_count"],
                    relationship_count=row["relationship_count"],
                    concept_count=row["concept_count"],
                    fact_count=row["fact_count"],
                    event_count=row["package_event_count"],
                    quality_score=row["quality_score"],
                    created_at=row["package_created_at"],
                )
            items.append(
                RunQueueItem(
                    run=self._from_row(row),
                    project_name=row["project_name"],
                    source_count=row["source_count"],
                    event_count=row["event_count"],
                    artifact_count=row["artifact_count"],
                    package=package,
                )
            )
        return items

    def update(self, run_id: str, *, status: RunStatus | None = None, current_stage: str | None = None, plan: ExecutionPlan | None = None, package_id: str | None = None, error_message: str | None = None, started: bool = False, completed: bool = False) -> Run:
        current = self.get_by_id(run_id)
        if current is None:
            raise KeyError(f"Run {run_id} not found")
        values = current.model_dump()
        if status is not None:
            values["status"] = status
        if current_stage is not None:
            values["current_stage"] = current_stage
        if plan is not None:
            values["plan"] = plan
        if package_id is not None:
            values["package_id"] = package_id
        if error_message is not None:
            values["error_message"] = error_message
        if started:
            values["started_at"] = datetime.now(UTC)
        if completed:
            values["completed_at"] = datetime.now(UTC)
        updated = Run.model_validate(values)
        with self.database.connect() as connection:
            connection.execute("""
                UPDATE runs SET status = ?, current_stage = ?, plan_json = ?, package_id = ?,
                    error_message = ?, started_at = ?, completed_at = ? WHERE id = ?
            """, (updated.status.value, updated.current_stage, updated.plan.model_dump_json() if updated.plan else None, updated.package_id, updated.error_message, updated.started_at.isoformat() if updated.started_at else None, updated.completed_at.isoformat() if updated.completed_at else None, run_id))
        return updated

    def add_event(self, run_id: str, *, stage: str, status: str, title: str, message: str, event_type: str) -> AgentEvent:
        with self.database.connect() as connection:
            sequence = connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_events WHERE run_id = ?", (run_id,)).fetchone()[0]
            event = AgentEvent(id=str(uuid4()), run_id=run_id, sequence=sequence, timestamp=datetime.now(UTC), stage=stage, status=status, title=title, message=message, event_type=event_type)
            connection.execute("INSERT INTO agent_events (id, run_id, sequence, timestamp, stage, status, title, message, event_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (event.id, event.run_id, event.sequence, event.timestamp.isoformat(), event.stage, event.status, event.title, event.message, event.event_type))
        return event

    def list_events(self, run_id: str, *, after_sequence: int = 0) -> list[AgentEvent]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM agent_events WHERE run_id = ? AND sequence > ? ORDER BY sequence", (run_id, after_sequence)).fetchall()
        return [AgentEvent.model_validate(dict(row)) for row in rows]

    def delete(self, run_id: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: object) -> Run:
        payload = dict(row)  # type: ignore[arg-type]
        run_payload = {
            "id": payload["id"],
            "project_id": payload["project_id"],
            "status": payload["status"],
            "current_stage": payload["current_stage"],
            "plan": json.loads(payload["plan_json"]) if payload.get("plan_json") else None,
            "package_id": payload.get("package_id"),
            "error_message": payload.get("error_message"),
            "created_at": payload["created_at"],
            "started_at": payload.get("started_at"),
            "completed_at": payload.get("completed_at"),
        }
        return Run.model_validate(run_payload)


class RunArtifactRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        run_id: str,
        *,
        stage: str,
        artifact_type: str,
        name: str,
        record_count: int = 0,
        parent_ids: list[str] | None = None,
        metadata: dict[str, object] | None = None,
        status: str = "completed",
    ) -> RunArtifact:
        artifact = RunArtifact(
            id=str(uuid4()),
            run_id=run_id,
            stage=stage,
            artifact_type=artifact_type,
            name=name,
            status=status,
            record_count=record_count,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO run_artifacts (
                    id, run_id, stage, artifact_type, name, status, record_count,
                    parent_ids_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.run_id,
                    artifact.stage,
                    artifact.artifact_type,
                    artifact.name,
                    artifact.status,
                    artifact.record_count,
                    json.dumps(artifact.parent_ids),
                    json.dumps(artifact.metadata),
                    artifact.created_at.isoformat(),
                ),
            )
        return artifact

    def list_for_run(self, run_id: str) -> list[RunArtifact]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM run_artifacts WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        artifacts: list[RunArtifact] = []
        for row in rows:
            payload = dict(row)
            payload["parent_ids"] = json.loads(payload.pop("parent_ids_json"))
            payload["metadata"] = json.loads(payload.pop("metadata_json"))
            artifacts.append(RunArtifact.model_validate(payload))
        return artifacts


class AssetPackageRepository:
    def __init__(self, database: Database, artifact_root: Path) -> None:
        self.database = database
        self.artifact_root = artifact_root

    def save(self, package: KnowledgeAssetPackage, run_id: str) -> AssetPackageSummary:
        project_dir = self.artifact_root / package.project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / f"{package.package_id}.json"
        temporary = project_dir / f".{package.package_id}.json.part"
        temporary.write_text(package.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        summary = AssetPackageSummary(package_id=package.package_id, project_id=package.project_id, run_id=run_id, entity_count=len(package.entities), relationship_count=len(package.relationships), concept_count=len(package.concepts), fact_count=len(package.facts), event_count=len(package.events), quality_score=package.quality_report.overall_score, created_at=package.created_at)
        with self.database.connect() as connection:
            connection.execute("""
                INSERT OR REPLACE INTO asset_packages (package_id, project_id, run_id, artifact_path,
                    entity_count, relationship_count, concept_count, fact_count, event_count, quality_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (summary.package_id, summary.project_id, summary.run_id, str(path), summary.entity_count, summary.relationship_count, summary.concept_count, summary.fact_count, summary.event_count, summary.quality_score, summary.created_at.isoformat()))
        return summary

    def latest_summary(self, project_id: str) -> AssetPackageSummary | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM asset_packages WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        return AssetPackageSummary.model_validate(dict(row)) if row else None

    def summary_for_run(self, run_id: str) -> AssetPackageSummary | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM asset_packages WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return AssetPackageSummary.model_validate(dict(row)) if row else None

    def load_latest(self, project_id: str) -> KnowledgeAssetPackage | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT artifact_path FROM asset_packages WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        if not row:
            return None
        return KnowledgeAssetPackage.model_validate_json(Path(row["artifact_path"]).read_text(encoding="utf-8"))

    def replace(self, package: KnowledgeAssetPackage) -> None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT artifact_path FROM asset_packages WHERE package_id = ?", (package.package_id,)).fetchone()
        if not row:
            raise KeyError("Asset package not found")
        path = Path(row["artifact_path"])
        temporary = path.with_name(f".{path.name}.part")
        temporary.write_text(package.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def record_review(self, project_id: str, package_id: str, asset_id: str, decision: str, note: str | None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO review_decisions (id, project_id, package_id, asset_id, decision, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), project_id, package_id, asset_id, decision, note, datetime.now(UTC).isoformat()),
            )

    def delete_for_run(self, run_id: str) -> int:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT artifact_path FROM asset_packages WHERE run_id = ?",
                (run_id,),
            ).fetchall()

        root = self.artifact_root.resolve()
        for row in rows:
            path = Path(row["artifact_path"])
            if path.is_symlink():
                raise ValueError("Refusing to delete a symbolic-link artifact")
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("Refusing to delete an artifact outside the configured artifact directory")
            if resolved.exists():
                if not resolved.is_file():
                    raise ValueError("Run artifact path is not a regular file")
                resolved.unlink()

        checkpoint_path = root / "langgraph-checkpoints.db"
        if checkpoint_path.is_symlink():
            raise ValueError("Refusing to modify a symbolic-link checkpoint database")
        if checkpoint_path.exists():
            if not checkpoint_path.is_file():
                raise ValueError("Checkpoint path is not a regular file")
            with sqlite3.connect(checkpoint_path) as checkpoint_connection:
                existing_tables = {
                    row[0]
                    for row in checkpoint_connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                for table in ("checkpoints", "writes"):
                    if table in existing_tables:
                        checkpoint_connection.execute(
                            f'DELETE FROM "{table}" WHERE thread_id = ?',
                            (run_id,),
                        )

        with self.database.connect() as connection:
            connection.execute("DELETE FROM asset_packages WHERE run_id = ?", (run_id,))
        return len(rows)
