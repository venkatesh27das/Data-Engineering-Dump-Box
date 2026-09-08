"""One transaction per run with typed query columns and full versioned JSON records."""

import json
from pathlib import Path

import duckdb

# Internal identifiers only. JSON payloads preserve nested fields without lossy flattening.
COLUMNS = {
    "runs": {"workbook_id": "VARCHAR", "stage": "VARCHAR", "created_at": "TIMESTAMP"},
    "workbooks": {
        "workbook_id": "VARCHAR",
        "filename": "VARCHAR",
        "file_hash": "VARCHAR",
        "sheet_count": "INTEGER",
        "formula_count": "INTEGER",
        "table_count": "INTEGER",
    },
    "sheets": {
        "sheet_id": "VARCHAR",
        "workbook_id": "VARCHAR",
        "name": "VARCHAR",
        "visibility": "VARCHAR",
        "max_row": "INTEGER",
        "max_column": "INTEGER",
    },
    "regions": {"region_id": "VARCHAR", "sheet_id": "VARCHAR", "range": "VARCHAR", "region_type": "VARCHAR"},
    "table_assets": {
        "table_id": "VARCHAR",
        "workbook_id": "VARCHAR",
        "sheet_id": "VARCHAR",
        "region_id": "VARCHAR",
        "table_name": "VARCHAR",
        "source_range": "VARCHAR",
        "row_count": "INTEGER",
        "parquet_path": "VARCHAR",
        "duckdb_table": "VARCHAR",
    },
    "formula_assets": {
        "formula_id": "VARCHAR",
        "workbook_id": "VARCHAR",
        "sheet_id": "VARCHAR",
        "cell": "VARCHAR",
        "formula": "VARCHAR",
        "parse_status": "VARCHAR",
    },
    "graph_edges": {"source": "VARCHAR", "target": "VARCHAR", "relationship": "VARCHAR"},
    "processing_warnings": {
        "code": "VARCHAR",
        "message": "VARCHAR",
        "sheet_name": "VARCHAR",
        "cell": "VARCHAR",
    },
    "text_assets": {"text_asset_id": "VARCHAR", "sheet_id": "VARCHAR", "content": "VARCHAR"},
    "image_assets": {"image_id": "VARCHAR", "sheet_id": "VARCHAR", "filename": "VARCHAR"},
    "chart_assets": {"chart_id": "VARCHAR", "sheet_id": "VARCHAR", "chart_type": "VARCHAR"},
    "feedback": {"region_id": "VARCHAR", "content": "VARCHAR"},
}


class StructuredStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, run_id: str, records: dict[str, list[dict]], tables: dict[str, Path]) -> None:
        with duckdb.connect(str(self.path)) as db:
            db.execute("BEGIN TRANSACTION")
            try:
                db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
                if not db.execute("SELECT count(*) FROM schema_version").fetchone()[0]:
                    db.execute("INSERT INTO schema_version VALUES (1)")
                for name, rows in records.items():
                    fields = COLUMNS[name]
                    ddl = ", ".join(f'"{field}" {dtype}' for field, dtype in fields.items())
                    db.execute(
                        f'CREATE TABLE IF NOT EXISTS "{name}" '
                        f"(run_id VARCHAR, ordinal INTEGER, {ddl}, payload JSON)"
                    )
                    existing = {
                        row[1]
                        for row in db.execute(f"PRAGMA table_info('{name}')").fetchall()
                    }
                    for field, dtype in fields.items():
                        if field not in existing:
                            db.execute(f'ALTER TABLE "{name}" ADD COLUMN "{field}" {dtype}')
                    db.execute(f'DELETE FROM "{name}" WHERE run_id = ?', [run_id])
                    if rows:
                        columns = ["run_id", "ordinal", *fields, "payload"]
                        column_sql = ", ".join(f'"{column}"' for column in columns)
                        placeholders = ", ".join("?" for _ in range(len(fields) + 3))
                        db.executemany(
                            f'INSERT INTO "{name}" ({column_sql}) VALUES ({placeholders})',
                            [
                                (run_id, i, *[row.get(field) for field in fields], json.dumps(row))
                                for i, row in enumerate(rows)
                            ],
                        )
                for name, parquet in tables.items():
                    db.execute(
                        f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM read_parquet(?)', [str(parquet)]
                    )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
