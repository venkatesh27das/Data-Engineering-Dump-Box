import os
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.storage.database import Database


class DemoResetSafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class DemoResetPlan:
    table_counts: dict[str, int]
    files: tuple[Path, ...]

    @property
    def record_count(self) -> int:
        return sum(self.table_counts.values())


RESET_TABLES = (
    "publications",
    "review_decisions",
    "asset_packages",
    "agent_events",
    "runs",
    "sources",
    "projects",
)


def _validated_root(path: Path) -> Path:
    if path.is_symlink():
        raise DemoResetSafetyError(f"Refusing symlinked reset root: {path}")
    root = path.resolve()
    if root == Path(root.anchor) or root == Path.home().resolve() or len(root.parts) < 3:
        raise DemoResetSafetyError(f"Refusing unsafe reset root: {root}")
    return root


def _managed_files(root: Path) -> list[Path]:
    root = _validated_root(root)
    if not root.exists():
        return []
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory in tuple(directories):
            candidate = current_path / directory
            if candidate.is_symlink():
                raise DemoResetSafetyError(f"Refusing symlink inside reset root: {candidate}")
        for filename in filenames:
            candidate = current_path / filename
            if filename == ".gitkeep":
                continue
            if candidate.is_symlink() or not candidate.is_file():
                raise DemoResetSafetyError(f"Refusing non-regular reset target: {candidate}")
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                raise DemoResetSafetyError(f"Reset target escaped configured root: {candidate}")
            files.append(resolved)
    return files


def build_reset_plan(settings: Settings, database: Database | None = None) -> DemoResetPlan:
    database = database or Database(settings.sqlite_path)
    database.initialize()
    with database.connect() as connection:
        table_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in RESET_TABLES
        }
    files = sorted({*_managed_files(settings.upload_path), *_managed_files(settings.artifact_path)})
    return DemoResetPlan(table_counts=table_counts, files=tuple(files))


def reset_local_demo(settings: Settings, database: Database | None = None) -> DemoResetPlan:
    database = database or Database(settings.sqlite_path)
    plan = build_reset_plan(settings, database)
    roots = (_validated_root(settings.upload_path), _validated_root(settings.artifact_path))

    for path in plan.files:
        if path.is_symlink() or not path.is_file() or not any(path.is_relative_to(root) for root in roots):
            raise DemoResetSafetyError(f"Reset target changed after preview: {path}")

    with database.connect() as connection:
        for table in RESET_TABLES:
            connection.execute(f"DELETE FROM {table}")

    for path in plan.files:
        path.unlink()

    for root in roots:
        if not root.exists():
            continue
        directories = sorted((path for path in root.rglob("*") if path.is_dir() and not path.is_symlink()), key=lambda path: len(path.parts), reverse=True)
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
    return plan


def count_neo4j_project_nodes(settings: Settings, project_id: str) -> int:
    if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
        raise DemoResetSafetyError("Neo4j Aura credentials are not configured")
    from neo4j import GraphDatabase

    with GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)) as driver:
        record = driver.execute_query(
            "MATCH (n:KnowledgeAsset {project_id: $project_id}) RETURN count(n) AS count",
            project_id=project_id,
            database_=settings.neo4j_database,
        ).records[0]
    return int(record["count"])


def reset_neo4j_project(settings: Settings, project_id: str) -> int:
    if not project_id.strip():
        raise DemoResetSafetyError("A non-empty Neo4j project id is required")
    if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
        raise DemoResetSafetyError("Neo4j Aura credentials are not configured")
    from neo4j import GraphDatabase

    with GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)) as driver:
        record = driver.execute_query(
            "MATCH (n:KnowledgeAsset {project_id: $project_id}) "
            "WITH collect(n) AS nodes FOREACH (node IN nodes | DETACH DELETE node) RETURN size(nodes) AS count",
            project_id=project_id,
            database_=settings.neo4j_database,
        ).records[0]
    return int(record["count"])
