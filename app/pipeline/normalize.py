import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.models.assets import FormulaAsset, TableAsset
from app.models.region import Region
from app.models.run import Run, WarningRecord
from app.models.workbook import Sheet, Workbook
from app.storage.structured_store import StructuredStore


def as_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [as_json(v) for v in value]
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(as_json(value), indent=2, ensure_ascii=False), encoding="utf-8")


def normalize(
    output: Path,
    run: Run,
    workbook: Workbook,
    sheets: list[Sheet],
    regions: list[Region],
    tables: list[TableAsset],
    formulas: list[FormulaAsset],
    graph: dict,
    warnings: list[WarningRecord],
    store: StructuredStore,
) -> None:
    write_json(output / "metadata/workbook.json", workbook)
    write_json(output / "metadata/sheets.json", sheets)
    write_json(output / "metadata/regions.json", regions)
    write_json(output / "metadata/table_assets.json", tables)
    with (output / "formulas/formulas.jsonl").open("w", encoding="utf-8") as stream:
        for formula in formulas:
            stream.write(formula.model_dump_json() + "\n")
    (output / "text/text_assets.jsonl").write_text("", encoding="utf-8")
    quality = {
        "overall_quality_score": None,
        "scope": "phase_1",
        "formula_parse_score": sum(f.parse_status == "parsed" for f in formulas) / len(formulas)
        if formulas
        else 1,
        "warnings": as_json(warnings),
        "note": "Full quality assessment is deferred to Phase 2.",
    }
    write_json(output / "quality/quality_report.json", quality)
    records = {
        "runs": [as_json(run)],
        "workbooks": [as_json(workbook)],
        "sheets": as_json(sheets),
        "regions": as_json(regions),
        "table_assets": as_json(tables),
        "formula_assets": as_json(formulas),
        "graph_edges": graph["edges"],
        "processing_warnings": as_json(warnings),
        "text_assets": [],
        "feedback": [],
    }
    store.save(run.run_id, records, {t.duckdb_table: output / t.parquet_path for t in tables})
    files = [
        {
            "path": str(p.relative_to(output)),
            "size_bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    ]
    write_json(
        output / "manifest.json",
        {
            "schema_version": 1,
            "phase": 1,
            "run_id": run.run_id,
            "workbook_id": workbook.workbook_id,
            "status": run.stage,
            "files": files,
            "counts": {
                "sheets": len(sheets),
                "tables": len(tables),
                "formulas": len(formulas),
                "dependencies": sum(e["relationship"] == "DEPENDS_ON" for e in graph["edges"]),
            },
            "warnings": as_json(warnings),
            "deferred": [
                "inferred_regions",
                "text_extraction",
                "visual_extraction",
                "quality_scoring",
                "ui",
                "agents",
                "embeddings",
            ],
        },
    )
