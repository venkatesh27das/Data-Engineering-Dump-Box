from datetime import UTC, datetime
from uuid import uuid4

from app.domain.publication import Publication, PublicationResult, PublicationStatus
from app.storage.database import Database


class PublicationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, project_id: str, package_id: str) -> Publication:
        publication = Publication(id=str(uuid4()), project_id=project_id, package_id=package_id, status=PublicationStatus.RUNNING, created_at=datetime.now(UTC))
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO publications (id, project_id, package_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
                (publication.id, project_id, package_id, publication.status.value, publication.created_at.isoformat()),
            )
        return publication

    def complete(self, publication_id: str, result: PublicationResult) -> Publication:
        completed_at = datetime.now(UTC)
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE publications SET status = ?, nodes_published = ?, relationships_published = ?, assets_skipped = ?, completed_at = ? WHERE id = ?",
                (PublicationStatus.COMPLETED.value, result.nodes_published, result.relationships_published, result.assets_skipped, completed_at.isoformat(), publication_id),
            )
            row = connection.execute("SELECT * FROM publications WHERE id = ?", (publication_id,)).fetchone()
        if row is None:
            raise KeyError("Publication not found")
        return Publication.model_validate(dict(row))

    def fail(self, publication_id: str, message: str) -> Publication:
        completed_at = datetime.now(UTC)
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE publications SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
                (PublicationStatus.FAILED.value, message[:2_000], completed_at.isoformat(), publication_id),
            )
            row = connection.execute("SELECT * FROM publications WHERE id = ?", (publication_id,)).fetchone()
        if row is None:
            raise KeyError("Publication not found")
        return Publication.model_validate(dict(row))

    def latest(self, project_id: str) -> Publication | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM publications WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        return Publication.model_validate(dict(row)) if row else None

    def list_for_project(self, project_id: str, limit: int = 20) -> list[Publication]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM publications WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, limit)).fetchall()
        return [Publication.model_validate(dict(row)) for row in rows]
