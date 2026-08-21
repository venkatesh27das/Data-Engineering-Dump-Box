import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as parquet

from app.storage.database import Database
from app.storage.local_store import LocalStore

STAGE_ORDER = [
    "profiling",
    "planning",
    "extracting",
    "interpreting",
    "validating",
    "packaging",
    "complete",
    "failed",
    "cancelled",
]

ASSET_FILES: dict[str, list[str]] = {
    "chart": ["metadata/charts.jsonl"],
    "conditional_format": ["metadata/conditional_formats.jsonl"],
    "connection": ["metadata/connections.jsonl"],
    "data_validation": ["metadata/data_validations.jsonl"],
    "external_link": ["metadata/external_links.jsonl"],
    "form": ["metadata/forms.jsonl"],
    "formula": ["metadata/formulas.jsonl"],
    "image": ["metadata/images.jsonl"],
    "macro": ["metadata/macros.jsonl"],
    "named_range": ["metadata/named_ranges.jsonl"],
    "pivot_table": ["metadata/pivots.jsonl"],
    "query": ["metadata/queries.jsonl"],
    "sheet": ["metadata/sheets.jsonl"],
    "table": ["metadata/tables.jsonl"],
    "semantic_unit": [
        "semantic_units/workbook_units.jsonl",
        "semantic_units/sheet_units.jsonl",
        "semantic_units/table_units.jsonl",
        "semantic_units/record_units.jsonl",
        "semantic_units/formula_units.jsonl",
        "semantic_units/visual_units.jsonl",
    ],
    "semantic_summary": ["workbook_summary.json"],
    "entity_candidate": ["graph/nodes.jsonl"],
    "relationship": ["graph/edges.jsonl"],
    "relationship_candidate": ["graph/edges.jsonl"],
}


def package_root(store: LocalStore, asset: dict[str, Any]) -> Path:
    return store.root / "workbooks" / asset["workbook_id"] / "runs" / asset["run_id"] / "package"


def read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_jsonl(path: Path, limit: int = 500) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if len(records) >= limit:
                    break
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(value)
    except (json.JSONDecodeError, OSError):
        return records
    return records


def _candidate_records(root: Path, asset_type: str) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for relative in ASSET_FILES.get(asset_type, []):
        file_path = root / relative
        if file_path.suffix == ".jsonl":
            candidates.extend((relative, item) for item in read_jsonl(file_path))
        else:
            value = read_json(file_path)
            if isinstance(value, dict):
                candidates.append((relative, value))
            elif isinstance(value, list):
                candidates.extend((relative, item) for item in value if isinstance(item, dict))
    return candidates


def _record_score(record: dict[str, Any], asset: dict[str, Any], raw_id: str) -> int:
    score = 0
    identifier_values = {
        str(value)
        for key, value in record.items()
        if (key == "id" or key.endswith("_id")) and isinstance(value, (str, int))
    }
    if raw_id in identifier_values:
        score += 100
    title_values = {
        str(record.get(key, "")).casefold()
        for key in ("name", "title", "label", "sheet_name")
        if record.get(key)
    }
    if asset["title"].casefold() in title_values:
        score += 25
    record_sheet = record.get("source_sheet") or record.get("sheet_name") or record.get("name")
    if asset.get("source_sheet") and record_sheet == asset["source_sheet"]:
        score += 12
    record_range = record.get("source_range") or record.get("range") or record.get("anchor_cell")
    if asset.get("source_range") and record_range == asset["source_range"]:
        score += 18
    return score


def find_asset_record(root: Path, asset: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    raw_id = asset["id"].split(":", 1)[-1]
    candidates = _candidate_records(root, asset["asset_type"])
    if not candidates:
        return None, None
    ranked = sorted(
        ((_record_score(record, asset, raw_id), source, record) for source, record in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, source, record = ranked[0]
    return (source, record) if best_score > 0 or len(candidates) == 1 else (None, None)


def _table_preview(root: Path, raw_id: str) -> tuple[str | None, list[dict[str, Any]]]:
    relative = f"structured_data/{raw_id.replace('.', '_')}.parquet"
    path = root / relative
    if not path.is_file():
        return None, []
    table = parquet.read_table(path).slice(0, 25)
    return relative, table.to_pylist()


def _image_preview(root: Path, record: dict[str, Any] | None) -> str | None:
    media_file = record.get("media_file") if record else None
    if not media_file:
        return None
    relative = f"media/images/{Path(str(media_file)).name}"
    return relative if (root / relative).is_file() else None


def _lineage_for_asset(root: Path, raw_id: str, title: str) -> list[dict[str, Any]]:
    rows = read_jsonl(root / "lineage" / "technical_lineage.jsonl", 1000)
    rows.extend(read_jsonl(root / "lineage" / "business_lineage.jsonl", 1000))
    title_key = title.casefold()
    related = []
    for row in rows:
        identifiers = {str(row.get("source_id", "")), str(row.get("target_id", ""))}
        description = str(row.get("relationship_description", "")).casefold()
        if raw_id in identifiers or (title_key and title_key in description):
            related.append(row)
        if len(related) >= 30:
            break
    return related


def get_asset_content(asset: dict[str, Any], store: LocalStore) -> dict[str, Any]:
    root = package_root(store, asset)
    source_file, record = find_asset_record(root, asset)
    raw_id = asset["id"].split(":", 1)[-1]
    data_file = None
    preview_rows: list[dict[str, Any]] = []
    if asset["asset_type"] == "table":
        data_file, preview_rows = _table_preview(root, raw_id)
    image_file = _image_preview(root, record)
    return {
        "asset": {
            key: asset[key]
            for key in (
                "id",
                "asset_type",
                "title",
                "summary",
                "source_sheet",
                "source_range",
                "confidence",
                "review_status",
            )
        },
        "content_kind": "image" if image_file else "table" if preview_rows else "json",
        "record": record,
        "record_source": source_file,
        "preview_rows": preview_rows,
        "preview_columns": list(preview_rows[0]) if preview_rows else [],
        "lineage": _lineage_for_asset(root, raw_id, asset["title"]),
        "preview_available": bool(image_file),
        "preview_file": image_file,
        "data_file": data_file,
    }


def resolve_package_file(root: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    target = (root / relative).resolve()
    resolved_root = root.resolve()
    if not target.is_relative_to(resolved_root) or not target.is_file():
        return None
    return target


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_run_trace(
    run_id: str, database: Database, store: LocalStore, run: dict[str, Any]
) -> dict[str, Any]:
    events = database.list_events(run_id)
    run_root = store.root / "workbooks" / run["workbook_id"] / "runs" / run_id
    root = run_root / "package"
    plan = read_json(run_root / "intermediate" / "processing_plan.json") or {}
    technical = read_jsonl(root / "lineage" / "technical_lineage.jsonl", 300)
    business = read_jsonl(root / "lineage" / "business_lineage.jsonl", 300)
    assets = database.list_assets(run_id)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(event["stage"], []).append(event)

    stages = []
    ordered_present = [stage for stage in STAGE_ORDER if stage in grouped]
    for index, stage in enumerate(ordered_present):
        stage_events = grouped[stage]
        started = _parse_time(stage_events[0]["timestamp"])
        next_started = None
        if index + 1 < len(ordered_present):
            next_started = _parse_time(grouped[ordered_present[index + 1]][0]["timestamp"])
        ended = next_started or _parse_time(run.get("completed_at")) or started
        duration = max(0.0, (ended - started).total_seconds()) if started and ended else None
        details: dict[str, Any] = {}
        for event in stage_events:
            details.update(event.get("details") or {})
        if stage == "failed" and run.get("error_message"):
            details.setdefault("error_message", run["error_message"])
        stages.append(
            {
                "stage": stage,
                "status": stage_events[-1]["status"],
                "progress_percent": stage_events[-1]["progress_percent"],
                "message": stage_events[-1]["message"],
                "started_at": stage_events[0]["timestamp"],
                "duration_seconds": round(duration, 3) if duration is not None else None,
                "event_count": len(stage_events),
                "details": details,
            }
        )

    return {
        "run_id": run_id,
        "status": run["status"],
        "current_stage": run["current_stage"],
        "progress_percent": run["progress_percent"],
        "error_message": run.get("error_message"),
        "events": events,
        "stages": stages,
        "processing_plan": plan,
        "lineage": {
            "technical": technical,
            "business": business,
            "technical_count": len(technical),
            "business_count": len(business),
        },
        "asset_counts": dict(sorted(Counter(asset["asset_type"] for asset in assets).items())),
    }
