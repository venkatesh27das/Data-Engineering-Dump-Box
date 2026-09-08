# Excel Intelligence

A local-first macOS application for inspecting `.xlsx` workbooks and producing
structured, traceable assets. The pipeline follows `CODEX.md`: deterministic
inspection comes first, and the local Workbook Intelligence Agent is used only
for ambiguous regions or an explicit review request.

The implemented MVP covers all five planned phases:

- deterministic upload, inspection, formulas, dependencies, Parquet, DuckDB,
  JSON, GraphML, and run metadata
- logical regions, inferred tables, narrative/comments, embedded images, chart
  inventory, and explainable quality scores
- Streamlit upload, results, and review/reprocess views
- optional LM Studio agent and VLM enrichment with bounded read-only tools, plus
  optional LibreOffice rendering
- workbook/sheet/table summaries and optional LanceDB semantic search

All deterministic processing works when LM Studio and LibreOffice are offline.
No macro, workbook code, external link, or data refresh is executed.

## Run locally on macOS

Python 3.11 or newer is required. From the repository root:

```bash
uv sync --extra dev
cp .env.example .env
uv run python scripts/create_sample_workbooks.py
uv run streamlit run app/ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501). Upload an `.xlsx` file or
choose **Try a sample**, then click **Process workbook**.

Without `uv`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python scripts/create_sample_workbooks.py
python -m streamlit run app/ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

The Streamlit application calls the pipeline directly, so FastAPI does not need
to run at the same time.

## Optional local services

LM Studio uses its OpenAI-compatible loopback endpoint. Put model identifiers in
`.env`; no model name is hard-coded:

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LLM_MODEL=your-local-instruct-model
VLM_MODEL=your-local-vision-model
EMBEDDING_MODEL=your-local-embedding-model
```

Start LM Studio's local server before processing. With no configured model, the
application keeps ambiguous regions available for manual review, uses
deterministic summaries, and skips embeddings and visual descriptions.

LibreOffice rendering is off by default. Install LibreOffice and set
`ENABLE_LIBREOFFICE_RENDER=true` to render selected regions. Rendering always
uses a temporary workbook copy and private profile. Workbooks with detectable
macros, external links/connections, query tables, embedded packages, or
potentially external formulas are not rendered. The upload is never overwritten.

## User flow

The Streamlit results page shows workbook metrics, quality, sheets, extracted
tables, formulas, dependencies, warnings, regions, narrative assets, images, and
charts. Native and inferred table assets can be downloaded as Parquet.

Low-confidence regions appear under **Review & reprocess**. A user can inspect a
bounded sample, save feedback, assign an expected type, or ask the local agent to
review it. Reprocessing creates a child run and preserves the parent files. If
embeddings are configured, semantic search is scoped to the selected run.

Formula cached values are preserved when present. This application does not
claim to calculate formulas; a missing cache produces a warning while the
expression and dependencies remain available.

## FastAPI

Run the API separately when programmatic access is needed:

```bash
uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Application health and implemented phase |
| GET | `/system/status` | Local model, enrichment, and LibreOffice status |
| POST | `/workbooks/upload` | Store a validated `.xlsx` upload |
| POST | `/workbooks/{workbook_id}/process` | Run the complete pipeline synchronously |
| GET | `/runs/{run_id}` | Read persisted run metadata |
| GET | `/runs/{run_id}/status` | Read the current processing stage |
| GET | `/workbooks/{workbook_id}` | Workbook metadata and latest run |
| GET | `/workbooks/{workbook_id}/sheets` | Sheet inventory |
| GET | `/workbooks/{workbook_id}/regions` | Regions and confidence |
| GET | `/workbooks/{workbook_id}/tables` | Native and inferred tables |
| GET | `/workbooks/{workbook_id}/text` | Text, descriptions, and summaries |
| GET | `/workbooks/{workbook_id}/formulas` | Paginated formula assets |
| GET | `/workbooks/{workbook_id}/graph` | Dependency graph JSON |
| GET | `/workbooks/{workbook_id}/images` | Extracted image metadata |
| GET | `/workbooks/{workbook_id}/charts` | Chart inventory and ranges |
| GET | `/workbooks/{workbook_id}/summaries` | Compact summaries |
| GET | `/regions/{region_id}` | Region and saved feedback |
| POST | `/regions/{region_id}/feedback` | Save review feedback |
| POST | `/regions/{region_id}/reprocess` | Create a child run for one region |
| POST | `/regions/{region_id}/render` | Optionally render one region |
| POST | `/search` | Search configured LanceDB embeddings |

Upload and process:

```bash
curl -F 'file=@tests/fixtures/fixture_cross_sheet.xlsx' \
  http://127.0.0.1:8000/workbooks/upload
curl -X POST http://127.0.0.1:8000/workbooks/WORKBOOK_ID/process
curl http://127.0.0.1:8000/workbooks/WORKBOOK_ID/regions
```

Processing is synchronous. A successful HTTP processing response can contain a
`FAILED` stage; inspect `stage` and `error`. Invalid uploads/values return 422,
unknown IDs return 404, unavailable optional services return 503, and concurrent
processing returns 409.

## Output and storage

Uploads are immutable under
`data/uploads/<workbook_id>/<sanitized_filename>`. Each run writes:

```text
data/outputs/<run_id>/
  manifest.json
  metadata/workbook.json
  metadata/sheets.json
  metadata/regions.json
  metadata/table_assets.json
  metadata/images.json
  metadata/charts.json
  metadata/summaries.json
  metadata/feedback.json
  tables/<table_id>.parquet
  text/text_assets.jsonl
  formulas/formulas.jsonl
  graph/dependency_graph.json
  graph/dependency_graph.graphml
  images/<image_id>.<extension>
  renders/<region_id>/*              # when enabled and available
  quality/quality_report.json
```

The manifest contains schema/phase information, parent and reprocessed-region
IDs, counts, warnings, and SHA-256 hashes. Tables retain workbook, sheet, region,
range, original headers, normalized columns, and source-row provenance. Blank
and totals rows inside explicit Excel table ranges are retained.

SQLite stores workbooks, runs, stages, region lookups, and feedback. DuckDB
stores versioned records in `runs`, `workbooks`, `sheets`, `regions`,
`table_assets`, `text_assets`, `formula_assets`, `image_assets`, `chart_assets`,
`graph_edges`, `processing_warnings`, and `feedback`. Each keeps useful typed
columns and its complete JSON payload. Phase 1 DuckDB tables are migrated in
place. Extracted table data is materialized under a run-unique identifier.

LanceDB tables are partitioned by embedding-model hash and vector dimension.
Only region-aware text, comments, summaries, and table descriptions are chunked;
individual cells are not automatically embedded. Vectors retain run, workbook,
sheet, region, asset type, range, and table provenance.

## Detection, agent, graph, and quality

Region detection gives explicit Excel tables precedence, recognizes merged
titles, and splits other occupied cells on wholly blank rows and columns. Density,
header shape, formulas, fills, borders, bold text, number formats, and location
produce an explainable type and confidence. Scores below
`REGION_AGENT_THRESHOLD` require review.

The single LangGraph agent follows inspect → reason → bounded tool call →
validate. It can read only the selected region through `inspect_range`,
`get_values`, `get_formulas`, and `get_styles`. Results are capped by
`MAX_TOOL_CELLS`, and the loop by `MAX_AGENT_STEPS`. Workbook text is untrusted.
Invalid model output records a warning and preserves deterministic results.

Dependency edges point from formula cells to their inputs (`DEPENDS_ON`). Large,
full-column, and full-row references remain compact range nodes. The parser
supports same-sheet and quoted cross-sheet A1 references, absolute/mixed
addresses, ranges, and case-insensitive workbook/sheet-scoped names. It reports
external, structured, 3D, dynamic, broken, array/data-table, and unresolved
references instead of inventing dependencies.

Quality is an unweighted mean of documented extraction coverage/confidence
components. It measures extraction quality, not business or formula correctness.

## Configuration and tests

All settings are environment driven; see [.env.example](.env.example). Resource
controls include upload/expanded-size limits, sheet/region caps, agent/tool/vector
limits, and model/render timeouts. `DATA_DIR` defaults to `./data`; derived paths
can be overridden. Use one Streamlit process or one Uvicorn worker per data
directory. A file lock serializes workbook/DuckDB writes across both interfaces.

```bash
uv run python scripts/create_sample_workbooks.py --output tests/fixtures
uv run pytest -q
uv run ruff check app scripts tests
```

Tests generate isolated workbooks and storage. Coverage includes upload limits,
inspection, hidden sheets, comments, merges, native/inferred tables, formulas,
named/cross-sheet references, graph assets, manifests, DuckDB migration,
images/charts, quality, parent-preserving reprocessing, bounded agent tools,
mocked/offline LM Studio, LanceDB search, rendering safeguards, API errors, and
Streamlit upload/sample flows.

The fixtures are `fixture_simple.xlsx`, `fixture_multi_region.xlsx`,
`fixture_cross_sheet.xlsx`, and `fixture_complex.xlsx`. The complex fixture has
five sheets, hidden states, names, comments, a merge, image, chart, formulas, and
multiple logical regions.

## Module boundaries

`pipeline/` owns extraction and optional enrichment orchestration. `agents/`
contains the exception-resolution graph. `tools/` exposes bounded inspection and
optional rendering. `llm/` contains the replaceable LM Studio transport.
`storage/` isolates SQLite, DuckDB, graph, and vectors. `services/` coordinates
operations; `ui/` and `api/` are thin local interfaces. These boundaries support
later migration without rewriting workbook parsing.
