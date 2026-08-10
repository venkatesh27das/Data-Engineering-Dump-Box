from datetime import UTC, datetime
from uuid import uuid4

from app.domain.projects import Project, ProjectCreate, ProjectUpdate, SourceAsset
from app.storage.database import Database


class ProjectRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, payload: ProjectCreate) -> Project:
        now = datetime.now(UTC)
        project = Project(id=str(uuid4()), created_at=now, updated_at=now, **payload.model_dump())
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    id, name, knowledge_objective, processing_mode, graph_depth,
                    review_low_confidence, max_tokens, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.knowledge_objective,
                    project.processing_mode.value,
                    project.graph_depth.value,
                    int(project.review_low_confidence),
                    project.max_tokens,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
        return project

    def get(self, project_id: str) -> Project | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._project_from_row(row) if row else None

    def update(self, project_id: str, payload: ProjectUpdate) -> Project | None:
        current = self.get(project_id)
        if current is None:
            return None
        values = current.model_dump()
        values.update(payload.model_dump(exclude_unset=True, exclude_none=True))
        values["updated_at"] = datetime.now(UTC)
        updated = Project.model_validate(values)
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE projects SET name = ?, knowledge_objective = ?, processing_mode = ?,
                    graph_depth = ?, review_low_confidence = ?, max_tokens = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.knowledge_objective,
                    updated.processing_mode.value,
                    updated.graph_depth.value,
                    int(updated.review_low_confidence),
                    updated.max_tokens,
                    updated.updated_at.isoformat(),
                    project_id,
                ),
            )
        return updated

    @staticmethod
    def _project_from_row(row: object) -> Project:
        return Project.model_validate(dict(row))  # type: ignore[arg-type]


class SourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, source: SourceAsset) -> SourceAsset:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    id, project_id, filename, original_filename, category, extension,
                    mime_type, size_bytes, storage_path, status, summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.id,
                    source.project_id,
                    source.filename,
                    source.original_filename,
                    source.category.value,
                    source.extension,
                    source.mime_type,
                    source.size_bytes,
                    source.storage_path,
                    source.status,
                    source.summary,
                    source.created_at.isoformat(),
                ),
            )
        return source

    def list_for_project(self, project_id: str) -> list[SourceAsset]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [SourceAsset.model_validate(dict(row)) for row in rows]

    def get(self, project_id: str, source_id: str) -> SourceAsset | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE project_id = ? AND id = ?",
                (project_id, source_id),
            ).fetchone()
        return SourceAsset.model_validate(dict(row)) if row else None

    def delete(self, project_id: str, source_id: str) -> SourceAsset | None:
        source = self.get(project_id, source_id)
        if source is None:
            return None
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM sources WHERE project_id = ? AND id = ?",
                (project_id, source_id),
            )
        return source
