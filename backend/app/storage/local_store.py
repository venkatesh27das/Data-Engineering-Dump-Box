import hashlib
import re
import shutil
from pathlib import Path

from app.core.config import Settings


class LocalStore:
    def __init__(self, settings: Settings):
        self.root = settings.storage_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name).name).strip(". ")
        return cleaned[:180] or "workbook.xlsx"

    def original_path(self, workbook_id: str, filename: str) -> Path:
        path = self.root / "workbooks" / workbook_id / "original" / self.sanitize_filename(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def run_path(self, workbook_id: str, run_id: str) -> Path:
        path = self.root / "workbooks" / workbook_id / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
