"""Bounded immutable uploads; OOXML is inspected without fetching relationships."""

import hashlib
import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from app.config.settings import Settings
from app.models.workbook import Workbook


class InvalidWorkbook(ValueError):
    pass


def ingest(stream: BinaryIO, filename: str, settings: Settings) -> Workbook:
    filename = re.sub(r"[^\w. -]", "_", filename.replace("\\", "/").split("/")[-1])
    if Path(filename).suffix.lower() != ".xlsx":
        raise InvalidWorkbook("Only .xlsx workbooks are supported; .xlsm/macros are unsupported")
    workbook_id, run_id = uuid4().hex, uuid4().hex
    folder = settings.upload_dir / workbook_id
    folder.mkdir()
    path = folder / filename
    size, digest = 0, hashlib.sha256()
    try:
        with path.open("xb") as dest:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_mb * 1024**2:
                    raise InvalidWorkbook("Upload exceeds MAX_UPLOAD_MB")
                digest.update(chunk)
                dest.write(chunk)
        with ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > settings.max_uncompressed_mb * 1024**2:
                raise InvalidWorkbook("Expanded workbook exceeds MAX_UNCOMPRESSED_MB")
            if any(i.flag_bits & 1 for i in archive.infolist()):
                raise InvalidWorkbook("Encrypted workbooks are unsupported")
            if not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(archive.namelist()):
                raise InvalidWorkbook("Not an OOXML workbook")
    except (BadZipFile, InvalidWorkbook, OSError) as exc:
        path.unlink(missing_ok=True)
        folder.rmdir()
        raise InvalidWorkbook(str(exc)) from exc
    return Workbook(
        workbook_id=workbook_id,
        run_id=run_id,
        filename=filename,
        file_path=str(path),
        file_hash=digest.hexdigest(),
        file_size_bytes=size,
    )
