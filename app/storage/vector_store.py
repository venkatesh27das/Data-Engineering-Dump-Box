"""Local LanceDB vectors, partitioned by embedding model and dimensionality."""

import hashlib
import re
from pathlib import Path

import lancedb
import pyarrow as pa


class VectorStore:
    def __init__(self, path: Path):
        self.db = lancedb.connect(str(path))

    @staticmethod
    def table_name(model: str, dimension: int) -> str:
        return "semantic_" + hashlib.sha256(model.encode()).hexdigest()[:16] + f"_{dimension}"

    def save(self, records: list[dict], model: str) -> None:
        if not records:
            return
        dimension = len(records[0]["vector"])
        name = self.table_name(model, dimension)
        schema = pa.schema(
            [
                pa.field(key, pa.list_(pa.float32(), dimension) if key == "vector" else pa.string())
                for key in records[0]
            ]
        )
        table = self.db.create_table(name, schema=schema, exist_ok=True)
        table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(records)

    def search(
        self, vector: list[float], model: str, limit: int = 10, run_id: str | None = None
    ) -> list[dict]:
        if run_id and not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run identifier")
        try:
            table = self.db.open_table(self.table_name(model, len(vector)))
        except (ValueError, FileNotFoundError):
            return []
        query = table.search(vector).limit(limit)
        if run_id:
            query = query.where(f"run_id = '{run_id}'", prefilter=True)
        return [{k: v for k, v in row.items() if k != "vector"} for row in query.to_list()]
