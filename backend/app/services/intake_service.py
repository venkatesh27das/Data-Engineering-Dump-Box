import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import WorkbookError
from app.storage.database import Database
from app.storage.local_store import LocalStore

SUPPORTED = {".xlsx", ".xlsm", ".xlsb"}


class IntakeService:
    def __init__(self, settings: Settings, database: Database, store: LocalStore):
        self.settings = settings
        self.database = database
        self.store = store

    def upload(self, upload: UploadFile, purpose: str, description: str) -> tuple[dict, dict]:
        original_name = self.store.sanitize_filename(upload.filename or "workbook.xlsx")
        extension = Path(original_name).suffix.lower()
        if extension not in SUPPORTED:
            raise WorkbookError("UNSUPPORTED_FILE_TYPE", "Choose an .xlsx, .xlsm, or .xlsb workbook.")
        workbook_id = f"wb_{uuid4().hex[:12]}"
        target = self.store.original_path(workbook_id, original_name)
        with target.open("wb") as output:
            shutil.copyfileobj(upload.file, output, length=1024 * 1024)
        size = target.stat().st_size
        if size == 0:
            target.unlink(missing_ok=True)
            raise WorkbookError("CORRUPT_WORKBOOK", "The uploaded workbook is empty.")
        if size > self.settings.max_upload_mb * 1024 * 1024:
            target.unlink(missing_ok=True)
            raise WorkbookError(
                "FILE_TOO_LARGE", f"The workbook must be {self.settings.max_upload_mb} MB or smaller."
            )
        self._validate_signature(target, extension)
        workbook = self.database.create_workbook(
            {
                "id": workbook_id,
                "original_filename": original_name,
                "display_name": original_name,
                "file_type": extension.removeprefix("."),
                "file_size_bytes": size,
                "sha256": self.store.sha256(target),
                "storage_uri": str(target),
                "purpose": purpose.strip() or "Knowledge extraction",
                "description": description.strip(),
            }
        )
        run = self.create_run(workbook_id)
        return workbook, run

    def create_run(
        self,
        workbook_id: str,
        parent_run_id: str | None = None,
        trigger_type: str = "initial",
        scope: str = "full_workbook",
    ) -> dict:
        current = self.database.list_runs(workbook_id=workbook_id)
        return self.database.create_run(
            {
                "id": f"run_{uuid4().hex[:12]}",
                "workbook_id": workbook_id,
                "parent_run_id": parent_run_id,
                "run_number": max((run["run_number"] for run in current), default=0) + 1,
                "trigger_type": trigger_type,
                "scope": scope,
            }
        )

    @staticmethod
    def _validate_signature(path: Path, extension: str) -> None:
        signature = path.read_bytes()[:8]
        if extension in {".xlsx", ".xlsm"}:
            if not signature.startswith(b"PK"):
                if signature.startswith(bytes.fromhex("D0CF11E0")):
                    raise WorkbookError(
                        "ENCRYPTED_WORKBOOK",
                        "This workbook appears encrypted or uses an unsupported binary format.",
                    )
                raise WorkbookError(
                    "CORRUPT_WORKBOOK", "The file does not contain a valid Excel Open XML workbook."
                )
            try:
                with zipfile.ZipFile(path) as archive:
                    infos = archive.infolist()
                    expanded = sum(info.file_size for info in infos)
                    compressed = max(1, sum(info.compress_size for info in infos))
                    if len(infos) > 50_000 or expanded > 2 * 1024**3 or expanded / compressed > 200:
                        raise WorkbookError(
                            "UNSAFE_ARCHIVE", "The workbook archive expands beyond safe processing limits."
                        )
                    if "xl/workbook.xml" not in archive.namelist():
                        raise WorkbookError(
                            "CORRUPT_WORKBOOK", "The file is missing required workbook metadata."
                        )
            except zipfile.BadZipFile as error:
                raise WorkbookError("CORRUPT_WORKBOOK", "The workbook archive is corrupt.") from error
        elif not signature.startswith(bytes.fromhex("D0CF11E0")):
            raise WorkbookError(
                "CORRUPT_WORKBOOK", "The file does not contain a valid binary Excel workbook."
            )
