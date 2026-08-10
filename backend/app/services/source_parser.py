from pathlib import Path

from app.domain.normalized import NormalizedSource
from app.domain.projects import SourceAsset
from app.tools.documents import parse_docx, parse_image, parse_pdf
from app.tools.structured import parse_ddl, parse_schema_csv, parse_schema_json


class UnsupportedSourceError(ValueError):
    pass


class SourceParser:
    def parse(self, source: SourceAsset) -> NormalizedSource:
        path = Path(source.storage_path)
        extension = source.extension.lower()
        if extension == ".sql":
            return parse_ddl(path.read_text(encoding="utf-8"), source_id=source.id, source_name=source.filename)
        if extension == ".json":
            return parse_schema_json(path.read_text(encoding="utf-8"), source_id=source.id, source_name=source.filename)
        if extension == ".csv":
            return parse_schema_csv(path.read_text(encoding="utf-8-sig"), source_id=source.id, source_name=source.filename)
        if extension == ".pdf":
            return parse_pdf(path, source_id=source.id, source_name=source.filename)
        if extension == ".docx":
            return parse_docx(path, source_id=source.id, source_name=source.filename)
        if extension in {".png", ".jpg", ".jpeg"}:
            return parse_image(path, source_id=source.id, source_name=source.filename)
        raise UnsupportedSourceError(f"No parser is registered for {extension}")
