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
    texts=None,
    images=None,
    charts=None,
    quality=None,
    feedback=None,
    summaries=None,
) -> None:
    write_json(output / "metadata/workbook.json", workbook)
    write_json(output / "metadata/sheets.json", sheets)
    write_json(output / "metadata/regions.json", regions)
    write_json(output / "metadata/table_assets.json", tables)
    with (output / "formulas/formulas.jsonl").open("w", encoding="utf-8") as stream:
        for formula in formulas:
            stream.write(formula.model_dump_json() + "\n")
    texts, images, charts = texts or [], images or [], charts or []
    (output / "text/text_assets.jsonl").write_text(
        "".join(t.model_dump_json() + "\n" for t in texts), encoding="utf-8"
    )
    write_json(output / "metadata/images.json", images)
    write_json(output / "metadata/charts.json", charts)
    write_json(output / "metadata/summaries.json", summaries or [])
    write_json(output / "metadata/feedback.json", feedback or [])
    quality = quality or {"warnings": as_json(warnings)}
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
        "text_assets": as_json(texts),
        "image_assets": as_json(images),
        "chart_assets": as_json(charts),
        "feedback": as_json(feedback or []),
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
            "phase": 5,
            "run_id": run.run_id,
            "workbook_id": workbook.workbook_id,
            "status": run.stage,
            "parent_run_id": run.parent_run_id,
            "reprocessed_region_id": run.reprocessed_region_id,
            "files": files,
            "counts": {
                "sheets": len(sheets),
                "tables": len(tables),
                "formulas": len(formulas),
                "dependencies": sum(e["relationship"] == "DEPENDS_ON" for e in graph["edges"]),
            },
            "warnings": as_json(warnings),
            "deferred": [],
        },
    )
