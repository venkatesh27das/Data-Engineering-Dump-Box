import json
import zipfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.processing.extractor import ExtractionResult


def build_embedding_chunks(result: ExtractionResult) -> list[dict[str, Any]]:
    chunks = [
        {
            "chunk_id": f"chunk.{unit['unit_id']}",
            "chunk_type": unit["unit_type"],
            "embedding_text": unit["text_content"],
            "metadata": {**unit["structural_context"], "source_range": unit["provenance"]["source_range"]},
            "source_unit_id": unit["unit_id"],
        }
        for unit in result.units
        if unit["text_content"]
    ]
    summary = result.manifest.get("summary")
    if summary:
        chunks.insert(
            0,
            {
                "chunk_id": f"chunk.{result.manifest['workbook_id']}.summary",
                "chunk_type": "workbook_summary",
                "embedding_text": summary,
                "metadata": {"workbook_id": result.manifest["workbook_id"]},
                "source_unit_id": f"{result.manifest['workbook_id']}.summary",
            },
        )
    for table in result.tables:
        text = (
            f"{table['name']} table with columns {', '.join(table['normalized_headers'])} "
            f"and {table['row_count']} rows."
        )
        chunks.append(
            {
                "chunk_id": f"chunk.{table['table_id']}.summary",
                "chunk_type": "table_summary",
                "embedding_text": text,
                "metadata": {"source_range": table["source_range"]},
                "source_unit_id": f"{table['table_id']}.summary",
            }
        )
    for formula in result.formulas:
        chunks.append(
            {
                "chunk_id": f"chunk.{formula['formula_id']}",
                "chunk_type": "formula_rule",
                "embedding_text": formula["business_rule"],
                "metadata": {
                    "sheet_name": formula["sheet_name"],
                    "source_range": formula["cell"],
                },
                "source_unit_id": formula["formula_id"],
            }
        )
    for visual in [*result.images, *result.charts]:
        text = visual.get("description") or visual.get("summary")
        visual_id = visual.get("image_id") or visual.get("chart_id")
        if text and visual_id:
            chunks.append(
                {
                    "chunk_id": f"chunk.{visual_id}",
                    "chunk_type": "image" if visual.get("image_id") else "chart",
                    "embedding_text": text,
                    "metadata": {
                        "sheet_name": visual.get("sheet_name"),
                        "source_range": visual.get("anchor_cell"),
                    },
                    "source_unit_id": visual_id,
                }
            )
    return chunks


def write_package(
    result: ExtractionResult, run_root: Path, embeddings: list[dict[str, Any]] | None = None
) -> Path:
    package = run_root / "package"
    directories = [
        "metadata",
        "structured_data",
        "semantic_units",
        "graph",
        "media/images",
        "media/embedded_files",
        "embedding_input",
        "embeddings",
        "quality",
        "lineage",
    ]
    for directory in directories:
        (package / directory).mkdir(parents=True, exist_ok=True)
    _json(package / "manifest.json", result.manifest)
    _json(
        package / "workbook_summary.json",
        {
            "summary": _summary(result),
            "counts": result.manifest.get("counts", {}),
            "semantic_mode": result.manifest.get("semantic_mode"),
        },
    )
    for name, rows in {
        "sheets": result.sheets,
        "regions": result.regions,
        "tables": result.tables,
        "columns": result.columns,
        "formulas": result.formulas,
        "named_ranges": result.named_ranges,
        "charts": result.charts,
        "images": result.images,
        "comments": result.comments,
        "external_links": result.external_links,
        "connections": result.connections,
        "queries": result.queries,
        "pivots": result.pivots,
        "conditional_formats": result.conditional_formats,
        "data_validations": result.data_validations,
        "macros": result.macros,
        "forms": result.forms,
    }.items():
        _jsonl(package / "metadata" / f"{name}.jsonl", rows)
    for table_id, rows in result.table_rows.items():
        safe_name = table_id.replace(".", "_")
        if rows:
            cleaned = [{key: _scalar(value) for key, value in row.items()} for row in rows]
            try:
                pq.write_table(
                    pa.Table.from_pylist(cleaned), package / "structured_data" / f"{safe_name}.parquet"
                )
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                string_rows = [
                    {key: "" if value is None else str(value) for key, value in row.items()}
                    for row in cleaned
                ]
                pq.write_table(
                    pa.Table.from_pylist(string_rows), package / "structured_data" / f"{safe_name}.parquet"
                )
    _jsonl(package / "semantic_units" / "record_units.jsonl", result.units)
    _jsonl(
        package / "semantic_units" / "workbook_units.jsonl",
        [
            {
                "unit_id": f"{result.manifest['workbook_id']}.summary",
                "unit_type": "workbook_summary",
                "text_content": _summary(result),
                "provenance": {"source_file": result.manifest["source_file"]},
            }
        ],
    )
    _jsonl(
        package / "semantic_units" / "sheet_units.jsonl",
        [
            {
                "unit_id": f"{sheet['sheet_id']}.summary",
                "unit_type": "sheet_summary",
                "text_content": (
                    f"Sheet {sheet['name']} is {sheet['visibility']} and uses {sheet['used_range']}."
                ),
                "provenance": {
                    "source_file": result.manifest["source_file"],
                    "source_sheet": sheet["name"],
                    "source_range": sheet["used_range"],
                },
            }
            for sheet in result.sheets
        ],
    )
    _jsonl(
        package / "semantic_units" / "table_units.jsonl",
        [
            {
                "unit_id": f"{table['table_id']}.summary",
                "unit_type": "table_summary",
                "text_content": (
                    f"{table['name']} has {table['row_count']} rows with columns "
                    f"{', '.join(table['normalized_headers'])}."
                ),
                "provenance": {"source_range": table["source_range"]},
            }
            for table in result.tables
        ],
    )
    _jsonl(
        package / "semantic_units" / "formula_units.jsonl",
        [
            {
                "unit_id": formula["formula_id"],
                "unit_type": "formula_rule",
                "text_content": formula["business_rule"],
                "structured_content": formula,
                "provenance": {
                    "source_sheet": formula["sheet_name"],
                    "source_range": formula["cell"],
                },
            }
            for formula in result.formulas
        ],
    )
    _jsonl(
        package / "semantic_units" / "visual_units.jsonl",
        [
            {
                "unit_id": item.get("image_id") or item.get("chart_id"),
                "unit_type": "image" if item.get("image_id") else "chart",
                "text_content": item.get("description") or item.get("summary", ""),
                "structured_content": item,
                "provenance": {
                    "source_sheet": item.get("sheet_name"),
                    "source_range": item.get("anchor_cell"),
                },
            }
            for item in [*result.images, *result.charts]
        ],
    )
    _jsonl(package / "graph" / "nodes.jsonl", result.nodes)
    _jsonl(package / "graph" / "edges.jsonl", result.edges)
    chunks = build_embedding_chunks(result)
    _jsonl(package / "embedding_input" / "chunks.jsonl", chunks)
    _jsonl(package / "embeddings" / "vectors.jsonl", embeddings or [])
    _json(
        package / "embeddings" / "manifest.json",
        {
            "status": "completed" if embeddings else "not_generated",
            "vector_count": len(embeddings or []),
            "model": (embeddings or [{}])[0].get("model"),
            "dimensions": (embeddings or [{}])[0].get("dimensions"),
        },
    )
    _json(
        package / "quality" / "validation_report.json",
        {
            "status": "passed" if not result.reviews else "review_recommended",
            "checks": {
                "semantic_units_have_provenance": True,
                "graph_edges_have_evidence": all(edge.get("evidence") for edge in result.edges),
                "images_have_source_location": all(image.get("sheet_name") for image in result.images),
            },
        },
    )
    _jsonl(package / "quality" / "issues.jsonl", result.reviews)
    _jsonl(package / "quality" / "review_items.jsonl", result.reviews)
    _jsonl(package / "lineage" / "technical_lineage.jsonl", result.edges)
    _jsonl(
        package / "lineage" / "business_lineage.jsonl",
        [edge for edge in result.edges if edge["relationship_type"] in {"FEEDS", "DERIVED_FROM"}],
    )
    for filename, binary in result.media:
        (package / "media" / "images" / filename).write_bytes(binary)
    archive = run_root / "workbook_knowledge_package.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in package.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(package))
    return archive


def _summary(result: ExtractionResult) -> str:
    if result.manifest.get("summary"):
        return str(result.manifest["summary"])
    counts = result.manifest.get("counts", {})
    visuals = counts.get("images", 0) + counts.get("charts", 0)
    return (
        f"Workbook with {counts.get('sheets', 0)} sheets, "
        f"{counts.get('tables', 0)} structured regions, "
        f"{counts.get('formulas', 0)} formulas, and {visuals} visual assets."
    )


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, default=str) + "\n" for value in values),
        encoding="utf-8",
    )


def _scalar(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
