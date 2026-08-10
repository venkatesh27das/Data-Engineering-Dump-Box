import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import Settings
from app.domain.projects import SourceAsset, SourceCategory
from app.repositories.projects import SourceRepository


class UploadValidationError(ValueError):
    pass


ALLOWED_EXTENSIONS: dict[str, tuple[SourceCategory, set[str]]] = {
    ".sql": (SourceCategory.STRUCTURED, {"text/plain", "application/sql", "application/octet-stream"}),
    ".json": (SourceCategory.STRUCTURED, {"application/json", "text/json", "text/plain", "application/octet-stream"}),
    ".csv": (SourceCategory.STRUCTURED, {"text/csv", "application/csv", "text/plain", "application/octet-stream"}),
    ".pdf": (SourceCategory.UNSTRUCTURED, {"application/pdf", "application/octet-stream"}),
    ".docx": (SourceCategory.UNSTRUCTURED, {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"}),
    ".png": (SourceCategory.UNSTRUCTURED, {"image/png", "application/octet-stream"}),
    ".jpg": (SourceCategory.UNSTRUCTURED, {"image/jpeg", "application/octet-stream"}),
    ".jpeg": (SourceCategory.UNSTRUCTURED, {"image/jpeg", "application/octet-stream"}),
}


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    return cleaned[:180] or "upload"


class UploadService:
    def __init__(self, settings: Settings, repository: SourceRepository) -> None:
        self.settings = settings
        self.repository = repository

    async def save(self, project_id: str, upload: UploadFile) -> SourceAsset:
        original_name = upload.filename or "upload"
        safe_name = sanitize_filename(original_name)
        extension = Path(safe_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UploadValidationError(f"Unsupported file type: {extension or 'unknown'}")

        category, allowed_mimes = ALLOWED_EXTENSIONS[extension]
        mime_type = (upload.content_type or "application/octet-stream").lower()
        if mime_type not in allowed_mimes:
            raise UploadValidationError(f"File content type {mime_type} does not match {extension}")

        source_id = str(uuid4())
        project_dir = self.settings.upload_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{source_id}_{safe_name}"
        destination = project_dir / stored_name
        temporary = project_dir / f".{stored_name}.part"
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        size = 0

        try:
            with temporary.open("xb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise UploadValidationError(
                            f"File exceeds the {self.settings.max_upload_mb} MB upload limit"
                        )
                    output.write(chunk)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        source = SourceAsset(
            id=source_id,
            project_id=project_id,
            filename=safe_name,
            original_filename=original_name,
            category=category,
            extension=extension,
            mime_type=mime_type,
            size_bytes=size,
            storage_path=str(destination),
            summary="Ready for analysis",
            created_at=datetime.now(UTC),
        )
        try:
            return self.repository.create(source)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def remove(self, project_id: str, source_id: str) -> SourceAsset | None:
        source = self.repository.get(project_id, source_id)
        if source is None:
            return None
        stored_path = Path(source.storage_path).resolve()
        allowed_root = (self.settings.upload_path / project_id).resolve()
        if not stored_path.is_relative_to(allowed_root):
            raise UploadValidationError("Stored source path is outside the project upload directory")
        stored_path.unlink(missing_ok=True)
        return self.repository.delete(project_id, source_id)
