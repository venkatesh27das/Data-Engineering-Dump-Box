import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.assets import KnowledgeAssetPackage
from app.domain.runs import AgentEvent, AssetPackageSummary, ExecutionPlan, Run, RunStatus
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

    @staticmethod
    def _from_row(row: object) -> Run:
        payload = dict(row)  # type: ignore[arg-type]
        payload["plan"] = json.loads(payload.pop("plan_json")) if payload.get("plan_json") else None
        return Run.model_validate(payload)


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
