# Excel Intelligence — Phase 1

A local Python application that turns `.xlsx` workbooks into sheet inventories,
native table Parquet files, preserved formulas, dependency graphs, and queryable
DuckDB metadata. `CODEX.md` is the project specification. This implementation
stops at **Phase 1 — Deterministic Core**.

## Run on macOS

Install Python 3.11 or newer (the macOS system Python may be older), then run
from this repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python scripts/create_sample_workbooks.py
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Alternatively, with `uv` installed: `uv sync --extra dev`, followed by
`uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000`.
Use **one Uvicorn worker** and one application instance per data directory;
DuckDB writes are serialized within that process. No Excel, LibreOffice,
LM Studio, cloud service, or network connection is needed at runtime.

Open [API documentation](http://127.0.0.1:8000/docs) for upload and processing.
This phase has no Streamlit interface.

```bash
curl -F 'file=@tests/fixtures/fixture_cross_sheet.xlsx' \
  http://127.0.0.1:8000/workbooks/upload
# Copy workbook_id from the response:
curl -X POST http://127.0.0.1:8000/workbooks/WORKBOOK_ID/process
curl http://127.0.0.1:8000/workbooks/WORKBOOK_ID/sheets
curl http://127.0.0.1:8000/workbooks/WORKBOOK_ID/formulas
```

Processing is synchronous. The response includes `run_id`, `stage`, `error`,
and `output_path`. A pipeline failure returns a persisted `FAILED` run so the
caller can inspect the cause; HTTP errors cover invalid uploads (422), missing
identifiers (404), and concurrent processing or unavailable results (409).
Check the returned stage even when HTTP status is 200.

## API

| Method | Path | Result |
| --- | --- | --- |
| GET | `/health` | Local application health and phase |
| POST | `/workbooks/upload` | Multipart `file`; immutable upload and initial run |
| POST | `/workbooks/{workbook_id}/process` | Process upload; repeated calls create a new run |
| GET | `/runs/{run_id}` | Persistent run metadata |
| GET | `/runs/{run_id}/status` | Current persisted stage |
| GET | `/workbooks/{workbook_id}` | Workbook metadata and latest run |
| GET | `/workbooks/{workbook_id}/sheets` | Sheet inventory for latest completed run |
| GET | `/workbooks/{workbook_id}/tables` | Native table assets and provenance |
| GET | `/workbooks/{workbook_id}/formulas?offset=0&limit=100` | Formula assets; limit 1–1000 |
| GET | `/workbooks/{workbook_id}/graph` | NetworkX graph serialized as nodes and edges |

Run-specific files remain accessible locally after reprocessing. Workbook asset
endpoints refer to the latest run and return 409 until that run completes.
Region feedback and remediation endpoints belong to later phases.

## Storage and output contract

Uploads are stored under `data/uploads/<workbook_id>/<sanitized_filename>` with
SHA-256 and size metadata. Source files are never rewritten. SQLite stores runs,
workbooks, and stage history in `run_events`, including failures. Each completed
run produces:

```text
data/outputs/<run_id>/
  manifest.json                      # schema version, counts, warnings, file hashes
  metadata/workbook.json
  metadata/sheets.json
  metadata/regions.json              # explicit native table regions only
  metadata/table_assets.json
  tables/<table_id>.parquet
  formulas/formulas.jsonl
  graph/dependency_graph.json
  graph/dependency_graph.graphml
  quality/quality_report.json
  text/text_assets.jsonl              # empty; deferred
  images/                            # reserved; deferred
  renders/                           # reserved; deferred
```

Parquet paths in assets are relative to their run directory. Table assets retain
original and normalized headers, sheet/region identity, source range, and source
row numbers. Blank rows and totals rows within native table ranges are retained.
Mixed-type columns fall back to strings with an explicit warning. Dates and
homogeneous numeric columns retain their types. Formulas in tables use cached
values, with nulls and warnings where caches are absent; formula expressions are
always stored separately.

`data/excel_intelligence.duckdb` contains `runs`, `workbooks`, `sheets`, `regions`,
`table_assets`, `formula_assets`, `graph_edges`, `processing_warnings`, and empty
`text_assets` / `feedback` tables. Each has `run_id`, `ordinal`, useful typed
query columns, and a full JSON `payload` for nested metadata. `schema_version`
starts at 1. Native table data is materialized under each asset's `duckdb_table`
identifier, unique per run. A run's DuckDB writes are transactional.

```python
import duckdb
with duckdb.connect('data/excel_intelligence.duckdb', read_only=True) as db:
    print(db.sql('SELECT filename, sheet_count, formula_count FROM workbooks'))
    print(db.sql('SELECT sheet_id, cell, formula, parse_status FROM formula_assets'))
    print(db.sql('SELECT source, target FROM graph_edges WHERE relationship = \'DEPENDS_ON\''))
```

## Dependency semantics and limits

The graph points **from a formula to its inputs** (`DEPENDS_ON`). Workbook,
sheet, region, table, cell, and range nodes retain provenance through `CONTAINS`.
Ranges are single nodes, including full-column/row references; they are never
expanded into millions of cells. For a range dependency, inspect its address
when determining whether a particular cell contributes to a formula. The graph
does not automatically expand range membership into transitive cell edges.

The conservative openpyxl-tokenizer parser supports A1 references, absolute and
mixed addresses, quoted sheet names and escaped apostrophes, same/cross-sheet
ranges, and case-insensitive workbook/sheet-scoped named ranges (including name
aliases). External references are recorded and never fetched. Unsupported
structured references, 3D references, dynamic `INDIRECT`/`OFFSET`, array/data-table
constructs, broken references, and unresolved names are reported as partial
parses. This is **reference extraction, not a formula calculation engine**.
The `formulas` evaluation package is therefore not needed in Phase 1.

Cached values may be missing or stale; this application preserves them without
claiming they were recalculated. Missing caches produce `COMPLETED_WITH_WARNINGS`.
The generated formula fixtures intentionally have no calculated caches.

Workbook inspection includes properties, hidden/veryHidden states, dimensions,
nonempty/formula counts, native tables, merged ranges, named ranges, comments,
hyperlinks, and image/chart counts. Image/chart extraction, inferred regions,
narrative extraction, full quality scoring, rendering, UI, embeddings, and all
agent/LM Studio features are deferred. Overall quality scores are null rather
than invented; the quality report contains parser coverage and warnings.

Uploads must be `.xlsx` OOXML ZIP files. Limits cover uploaded bytes, expanded
ZIP size, and inspected sheet dimensions. `.xls`, `.xlsm`, encrypted files, and
invalid packages are rejected or recorded as failed inspection. Detectable
macro/data-connection parts are reported; no VBA, external links, or external
data refresh is executed. Optional features never trigger a model call.

## Configuration

`app/config/settings.py` reads environment variables and `.env`. `DATA_DIR`
defaults to `./data`; upload/output/database paths derive from it unless explicitly
overridden. Limits are `MAX_UPLOAD_MB`, `MAX_UNCOMPRESSED_MB`, and
`MAX_SHEET_CELLS`. The latter limits the rectangular sheet area traversed during
inspection, so extremely sparse sheets with distant formatting may need a larger
limit. Configuration fields for later phases are documented in `.env.example`
but do not enable those features in Phase 1.

## Tests and fixtures

```bash
python scripts/create_sample_workbooks.py --output tests/fixtures
python -m pytest -q
python -m ruff check app scripts tests
```

Tests generate their own isolated workbooks and data directories. They cover
upload validation and limits, metadata persistence, sheet inventory, hidden
sheets, comments and merged ranges, native tables, mixed types and blanks,
formula/cached-value preservation, references and named scopes, compact graph
ranges, manifest hashes, JSON/Parquet/DuckDB/GraphML outputs, concurrent-writer
rejection, failed runs, empty workbooks, and reprocessing.

The four reproducible fixtures are `fixture_simple.xlsx`,
`fixture_multi_region.xlsx`, `fixture_cross_sheet.xlsx`, and `fixture_complex.xlsx`.
The complex fixture has five sheets, hidden/veryHidden sheets, named ranges,
a comment, hyperlink, merged cells, an embedded image, and a chart.

## Module boundaries

`pipeline/` handles deterministic ingestion, inspection, extraction, parsing,
and normalization. `graph/` builds the in-memory NetworkX graph. `storage/`
isolates SQLite, DuckDB, and graph persistence. `services/` coordinates API calls
and local write serialization. `models/` contains Pydantic schemas. Empty
`ui/`, `agents/`, `llm/`, and `tools/` packages reserve later extension points;
there are no placeholder agent implementations or model dependencies.
