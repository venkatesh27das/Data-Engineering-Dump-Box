# CODEX.md — Local Excel / Workbook Intelligence Platform

## 1. Project Objective

Build a **local-first Excel / Workbook Intelligence platform** that runs on a MacBook and processes `.xlsx` workbooks containing:

- multiple sheets
- structured Excel tables
- multiple logical tables within a single sheet
- formulas
- cross-sheet formula dependencies
- named ranges
- merged cells
- free-text/narrative regions
- comments/notes
- images
- charts
- hidden sheets

The system must convert a workbook into normalized assets that can later be used for:

- structured analytics
- embeddings / vector search
- entity extraction
- graph construction
- downstream RAG / agentic use cases
- future migration to Databricks / Azure

The core architecture principle is:

> **Deterministic pipeline first; agentic reasoning only for ambiguous, low-confidence, or failed regions.**

Do **not** implement Excel processing as a pure LLM/agent workflow.

---

## 2. Primary User Experience

The initial product should be a simple local application.

### Main flow

1. User opens local web UI.
2. User uploads an `.xlsx` workbook.
3. System creates a processing run.
4. Workbook is inspected deterministically.
5. Sheets, regions, formulas, tables, text, images, charts and relationships are extracted.
6. Low-confidence regions are escalated to the Workbook Intelligence Agent.
7. Outputs are normalized and stored locally.
8. UI displays:
   - workbook summary
   - processing status
   - sheet inventory
   - tables found
   - formulas found
   - dependency count
   - images/charts found
   - quality score
   - regions requiring review
9. User can inspect results.
10. User can provide feedback and reprocess a selected sheet/region.

Keep the UI intentionally simple.

---

# 3. Technology Stack

Use the following stack unless there is a strong technical reason not to.

## Application

- Python 3.11+
- FastAPI
- Pydantic v2
- Streamlit

## Excel / OOXML

Primary:
- `openpyxl`

Additional:
- `lxml`
- Python `zipfile`

Use OOXML directly only when openpyxl does not expose enough detail.

## Tabular processing

Preferred:
- `polars`

Allowed:
- `pandas` where library interoperability requires it

## Formula processing

Use:
- `formulas` Python package where useful
- custom formula reference parser where necessary

Do not depend on Microsoft Excel.

## Graph

Use:
- `networkx`

Persist initial graph assets as:
- JSON
- GraphML

Do not introduce Neo4j in MVP.

## Rendering

Use local LibreOffice headless mode when installed.

Use:
- `soffice --headless`

Purpose:
- recalculate temporary workbook copies when requested
- render workbooks/sheets to PDF
- support visual inspection

Use:
- `PyMuPDF` (`fitz`)

for PDF to image conversion.

The system must degrade gracefully if LibreOffice is unavailable.

## LLM / VLM

Use LM Studio through its local OpenAI-compatible server.

Default base URL:

```text
http://localhost:1234/v1
```

Do not hard-code model names.

Read models from environment/configuration.

Suggested configuration:

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
LLM_MODEL=
VLM_MODEL=
EMBEDDING_MODEL=
```

If a VLM is not configured, visual reasoning should be skipped rather than fail the full run.

## Agent framework

Use:
- `langgraph`

Do not use a multi-agent architecture for MVP.

Implement one:

> **Workbook Intelligence Agent**

The agent should only be invoked when deterministic processing returns low confidence, an ambiguous region, or an explicit reprocessing request.

## Storage

Structured assets:
- Parquet
- DuckDB

Run metadata:
- SQLite initially

Vectors:
- LanceDB

Graph:
- NetworkX + JSON/GraphML

Raw and normalized files:
- local filesystem

---

# 4. High-Level Architecture

```text
                         Excel Workbook
                              .xlsx
                                |
                                v
                    +-----------------------+
                    | Workbook Ingestion    |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Workbook Inspector    |
                    | openpyxl / OOXML      |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Workbook Inventory    |
                    | sheets / cells /      |
                    | tables / formulas /   |
                    | images / charts /     |
                    | comments / names      |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Sheet Structure       |
                    | Analyzer              |
                    +-----------+-----------+
                                |
              +-----------------+------------------+
              |                 |                  |
              v                 v                  v
       Structured Tables      Text            Images/Charts
              |                 |                  |
              +-----------------+------------------+
                                |
                                v
                    +-----------------------+
                    | Formula & Dependency  |
                    | Analyzer              |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    | Confidence / Quality  |
                    | Assessment            |
                    +-----------+-----------+
                                |
                         low confidence?
                         /            \
                       no              yes
                       |                |
                       |                v
                       |      +--------------------+
                       |      | Workbook Agent     |
                       |      | LM Studio + Tools  |
                       |      +---------+----------+
                       |                |
                       +----------------+
                                |
                                v
                    +-----------------------+
                    | Normalization         |
                    +-----------+-----------+
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
         DuckDB /          LanceDB             NetworkX
          Parquet           Vectors              Graph
```

---

# 5. Repository Structure

Create the project approximately as follows:

```text
excel-intelligence/
|
|-- app/
|   |-- __init__.py
|   |
|   |-- api/
|   |   |-- __init__.py
|   |   `-- main.py
|   |
|   |-- ui/
|   |   `-- streamlit_app.py
|   |
|   |-- config/
|   |   |-- __init__.py
|   |   `-- settings.py
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- workbook.py
|   |   |-- region.py
|   |   |-- assets.py
|   |   `-- run.py
|   |
|   |-- pipeline/
|   |   |-- __init__.py
|   |   |-- orchestrator.py
|   |   |-- ingest.py
|   |   |-- inspect_workbook.py
|   |   |-- detect_regions.py
|   |   |-- extract_tables.py
|   |   |-- extract_text.py
|   |   |-- extract_images.py
|   |   |-- extract_charts.py
|   |   |-- parse_formulas.py
|   |   |-- normalize.py
|   |   `-- quality.py
|   |
|   |-- agents/
|   |   |-- __init__.py
|   |   `-- workbook_agent.py
|   |
|   |-- tools/
|   |   |-- __init__.py
|   |   |-- workbook_tools.py
|   |   |-- formula_tools.py
|   |   |-- rendering_tools.py
|   |   `-- extraction_tools.py
|   |
|   |-- graph/
|   |   |-- __init__.py
|   |   `-- dependency_graph.py
|   |
|   |-- llm/
|   |   |-- __init__.py
|   |   `-- lmstudio_client.py
|   |
|   |-- storage/
|   |   |-- __init__.py
|   |   |-- metadata_store.py
|   |   |-- structured_store.py
|   |   |-- vector_store.py
|   |   `-- graph_store.py
|   |
|   `-- services/
|       |-- run_service.py
|       `-- feedback_service.py
|
|-- data/
|   |-- uploads/
|   |-- processed/
|   `-- outputs/
|
|-- tests/
|   |-- unit/
|   |-- integration/
|   `-- fixtures/
|
|-- scripts/
|   `-- create_sample_workbooks.py
|
|-- .env.example
|-- pyproject.toml
|-- README.md
`-- CODEX.md
```

Avoid unnecessary abstraction layers in the first implementation.

---

# 6. Core Data Model

Use Pydantic models.

## Workbook

Minimum fields:

```text
workbook_id
run_id
filename
file_path
file_hash
file_size_bytes
created_at
sheet_count
formula_count
table_count
image_count
chart_count
named_range_count
hidden_sheet_count
processing_status
overall_quality_score
```

## Sheet

```text
sheet_id
workbook_id
name
index
visibility
max_row
max_column
non_empty_cells
formula_count
table_count
image_count
chart_count
merged_range_count
region_count
```

## Region

```text
region_id
sheet_id
range
region_type
confidence
detected_by
requires_agent_review
agent_review_status
```

Allowed initial region types:

```text
title
header
table
summary_table
kpi_block
narrative
notes
image
chart
empty
unknown
```

## TableAsset

```text
table_id
workbook_id
sheet_id
region_id
table_name
source_range
columns
row_count
parquet_path
duckdb_table
quality_score
```

## TextAsset

```text
text_asset_id
workbook_id
sheet_id
region_id
source_range
content
content_type
embedding_status
```

## FormulaAsset

```text
formula_id
workbook_id
sheet_id
cell
formula
cached_value
referenced_cells
referenced_ranges
referenced_sheets
external_reference
parse_status
```

## GraphEdge

```text
source
target
relationship
metadata
```

Initial relationships:

```text
DEPENDS_ON
BELONGS_TO
DERIVED_FROM
CONTAINS
REFERENCES
```

---

# 7. Workbook Inspection Requirements

Implement deterministic workbook inspection first.

For each workbook capture:

- workbook filename
- workbook metadata
- sheet names
- sheet ordering
- visible / hidden / veryHidden state
- sheet dimensions
- non-empty cells
- formulas
- cached values where available
- merged cells
- Excel Table objects
- named ranges
- comments
- hyperlinks
- images
- charts
- external links where identifiable
- presence of macros / unsupported features where detectable

Never execute VBA or macros.

For `.xlsm`, either:
1. reject in MVP with clear unsupported status, or
2. inspect safely without macro execution if implementation is straightforward.

Primary MVP support is `.xlsx`.

---

# 8. Dual Workbook Loading

Where useful, load workbooks in both modes:

```python
formula_wb = openpyxl.load_workbook(
    path,
    data_only=False,
    read_only=False
)

value_wb = openpyxl.load_workbook(
    path,
    data_only=True,
    read_only=False
)
```

Preserve both:

- formula expression
- cached/computed value

Do not silently replace formulas with values.

---

# 9. Sheet Region Detection

This is a core capability.

A sheet may contain multiple logical regions and cannot be assumed to equal one table.

Implement deterministic region detection using features including:

- contiguous non-empty cells
- blank row separators
- blank column separators
- cell density
- merged cells
- borders
- fills
- fonts
- bold text
- number formats
- formula density
- repeated data types
- header-like rows
- row/column continuity
- Excel Table ranges
- relative location
- neighboring labels
- known titles

Return regions with confidence scores.

Example:

```json
{
  "sheet": "Executive Summary",
  "regions": [
    {
      "range": "A1:H2",
      "type": "title",
      "confidence": 0.98
    },
    {
      "range": "A4:H20",
      "type": "summary_table",
      "confidence": 0.91
    },
    {
      "range": "A23:H26",
      "type": "narrative",
      "confidence": 0.84
    },
    {
      "range": "J4:N10",
      "type": "unknown",
      "confidence": 0.55,
      "requires_agent_review": true
    }
  ]
}
```

Initial agent escalation threshold:

```text
confidence < 0.70
```

Make threshold configurable.

Do not send the whole workbook to the LLM merely because one region is ambiguous.

---

# 10. Table Extraction

Handle two table types.

## A. Native Excel Tables

If openpyxl exposes an Excel Table object:

- use its explicit range
- preserve table name
- preserve headers
- convert to Polars DataFrame
- normalize column names
- write Parquet
- register in DuckDB

## B. Inferred Tables

For detected tabular regions:

- identify header row
- infer columns
- preserve original cell coordinates
- convert to DataFrame
- avoid dropping rows silently
- record parsing warnings
- assign quality score

Keep provenance from each table back to:

```text
workbook -> sheet -> region -> cell range
```

---

# 11. Formula Processing

Extract every formula cell.

For each formula determine where possible:

- same-sheet cell dependencies
- same-sheet range dependencies
- cross-sheet cell dependencies
- cross-sheet range dependencies
- named range references
- external workbook references
- unsupported/dynamic constructs

Examples:

```text
=SUM(D5:D20)
=Sales!D20
=Sales!D20/Targets!B4
='Lookup Values'!C7
```

Produce normalized dependency edges.

Example:

```text
Summary!B7 --DEPENDS_ON--> Sales!D20
Summary!B7 --DEPENDS_ON--> Targets!B4
```

Avoid expanding very large ranges into millions of individual graph nodes.

For a formula referencing a range such as:

```text
Sales!D5:D50000
```

represent the range as a range node or summarized dependency unless cell-level expansion is explicitly requested.

---

# 12. Formula Graph

Use NetworkX.

Recommended node types:

```text
WORKBOOK
SHEET
REGION
TABLE
CELL
RANGE
NAMED_RANGE
IMAGE
CHART
TEXT_ASSET
```

Recommended edges:

```text
CONTAINS
BELONGS_TO
DEPENDS_ON
REFERENCES
DERIVED_FROM
```

Graph must support questions such as:

- What formulas contribute to this KPI?
- Which sheets are dependencies of the Summary sheet?
- Which cells depend on Targets!B4?
- Which tables contribute to an Executive Summary?
- Which sheets contain no dependencies?

Persist:

```text
dependency_graph.json
dependency_graph.graphml
```

---

# 13. Free Text Extraction

Extract narrative information including:

- titles
- notes
- comments
- text blocks
- management commentary
- instructions
- labels not belonging to tables

Preserve:

```text
workbook
sheet
range
region_type
content
```

Chunking must be region-aware.

Do not split every cell into an independent vector chunk.

Preferred semantic unit:

```text
workbook -> sheet -> region
```

---

# 14. Images and Charts

## Images

Extract embedded images where openpyxl/OOXML permits.

Store locally:

```text
data/outputs/<run_id>/images/
```

Create metadata containing:

```text
sheet
anchor/cell location
filename
mime type
width
height
```

If a VLM is configured:
- optionally generate a description
- optionally classify visual content
- store description as a TextAsset

## Charts

For MVP:

- identify chart objects
- capture title/type if available
- record anchor
- record referenced series/ranges where possible
- optionally render visually
- optionally send rendered visual to VLM

Do not attempt to reconstruct every Excel chart behavior.

---

# 15. LibreOffice Rendering

Implement a rendering service.

Responsibilities:

- detect whether LibreOffice is installed
- expose availability in UI/system status
- copy workbook to temporary path before modifying/recalculating
- never overwrite original upload
- optionally recalculate copy
- export workbook to PDF
- convert PDF pages to PNG using PyMuPDF

Example command pattern:

```bash
soffice --headless --convert-to pdf --outdir <output_dir> <input.xlsx>
```

Treat rendering as optional enrichment.

The processing pipeline must still produce structured/formula outputs if rendering fails.

---

# 16. LM Studio Client

Implement one centralized LM Studio client.

Use OpenAI-compatible APIs.

Configuration must be environment-driven.

Methods should support:

```text
chat_completion()
structured_completion()
tool_calling()
vision_completion()
embedding()
health_check()
```

Use structured JSON responses for agent classifications whenever possible.

Set timeouts.

Handle LM Studio being unavailable without crashing deterministic processing.

---

# 17. Workbook Intelligence Agent

Implement one LangGraph agent.

Purpose:

> Resolve ambiguity and perform selective remediation, not primary workbook parsing.

Agent invocation scenarios:

1. Region confidence below threshold.
2. Conflicting deterministic signals.
3. User requests reprocessing.
4. Table/header inference fails.
5. Visually complex dashboard or summary region.
6. Quality validation finds suspicious extraction.

Do not invoke agent for:

- listing sheets
- extracting known Excel tables
- extracting formulas
- identifying explicit formula references
- enumerating comments
- normal cell reading
- image extraction

---

# 18. Agent Tools

Expose narrow, safe tools such as:

```text
list_sheets(workbook_id)

get_sheet_summary(workbook_id, sheet_name)

inspect_range(workbook_id, sheet_name, cell_range)

get_values(workbook_id, sheet_name, cell_range)

get_formulas(workbook_id, sheet_name, cell_range)

get_styles(workbook_id, sheet_name, cell_range)

get_tables(workbook_id, sheet_name)

get_named_ranges(workbook_id)

get_images(workbook_id, sheet_name)

get_charts(workbook_id, sheet_name)

render_sheet(workbook_id, sheet_name)

render_range(workbook_id, sheet_name, cell_range)

trace_dependencies(workbook_id, sheet_name, cell)

extract_region(workbook_id, sheet_name, cell_range, extraction_type)
```

Tool outputs must be bounded.

Never return an entire massive workbook through one tool result.

---

# 19. Agent Decision Pattern

The agent should follow:

```text
Inspect
  |
Reason
  |
Call smallest required tool
  |
Observe
  |
Need more evidence?
 /             \
yes             no
 |               |
Call tool      Classify / remediate
                 |
              Validate
                 |
              Return result
```

Set maximum tool iterations.

Suggested MVP:

```text
MAX_AGENT_STEPS = 8
```

---

# 20. Agent Response Schema

Require structured output.

Example:

```json
{
  "region_id": "region_123",
  "classification": "kpi_block",
  "confidence": 0.91,
  "reason_summary": "Compact label-value formula section with consistent KPI formatting.",
  "recommended_processing": "extract_as_key_value_summary",
  "requires_human_review": false
}
```

Store only concise reason summaries.

Do not depend on hidden chain-of-thought.

---

# 21. Confidence and Quality

Create explainable quality metrics.

Suggested components:

```text
structure_detection_score
table_extraction_score
formula_parse_score
dependency_resolution_score
text_extraction_score
visual_processing_score
agent_confidence
```

Overall workbook score should be an aggregate.

Store warnings separately.

Examples:

```text
BROKEN_FORMULA_REFERENCE
EXTERNAL_WORKBOOK_REFERENCE
LOW_CONFIDENCE_REGION
UNSUPPORTED_MACRO
VLM_UNAVAILABLE
LIBREOFFICE_UNAVAILABLE
TABLE_HEADER_UNCERTAIN
```

---

# 22. Local Output Contract

Each processing run should produce:

```text
data/outputs/<run_id>/
|
|-- manifest.json
|
|-- metadata/
|   |-- workbook.json
|   |-- sheets.json
|   `-- regions.json
|
|-- tables/
|   |-- <table_id>.parquet
|   `-- ...
|
|-- text/
|   `-- text_assets.jsonl
|
|-- formulas/
|   `-- formulas.jsonl
|
|-- graph/
|   |-- dependency_graph.json
|   `-- dependency_graph.graphml
|
|-- images/
|   `-- ...
|
|-- renders/
|   `-- ...
|
`-- quality/
    `-- quality_report.json
```

---

# 23. DuckDB Schema

Create initial logical tables such as:

```text
runs
workbooks
sheets
regions
table_assets
text_assets
formula_assets
graph_edges
processing_warnings
feedback
```

Keep database schema simple and versionable.

---

# 24. Vector Storage

Use LanceDB.

Embed only useful semantic content.

Candidates:

- narrative regions
- comments
- workbook summary
- sheet summaries
- table descriptions
- chart/VLM descriptions
- optionally row groups for selected tables

Do not automatically embed every cell.

Each vector record should retain metadata:

```text
workbook_id
sheet_name
region_id
asset_type
source_range
table_id
```

---

# 25. Workbook / Sheet Summaries

Use LLM only after deterministic extraction has produced compact metadata.

Do not pass raw full workbook contents.

Possible input:

```json
{
  "sheet": "Executive Summary",
  "tables": ["Regional Performance"],
  "kpi_regions": ["J4:N10"],
  "narrative_regions": ["A23:H26"],
  "formula_dependency_sheets": ["Sales", "Targets"],
  "images": 1,
  "charts": 2
}
```

Generate concise summaries such as:

```text
Executive summary sheet containing regional performance KPIs,
management commentary and two charts. Metrics are primarily
derived from Sales and Targets sheets.
```

---

# 26. UI Requirements

Use Streamlit.

Keep MVP to three views.

## View 1 — Upload / Process

Show:

- drag/drop `.xlsx`
- file name
- Process button
- LM Studio status
- LibreOffice status
- current processing stage
- basic completion status

## View 2 — Workbook Results

Header metrics:

```text
Sheets
Tables
Formulas
Images
Charts
Dependencies
Quality Score
Review Required
```

Below:

- sheet list
- discovered assets
- warnings
- low-confidence regions

Allow user to inspect a sheet.

## View 3 — Review / Reprocess

For a selected low-confidence region show:

- sheet
- cell range
- detected type
- confidence
- sample values
- optional render
- agent result

User can provide:

```text
feedback text
expected region type
reprocess action
```

Button:

```text
Reprocess Region
```

Do not build authentication for MVP.

---

# 27. API Requirements

Implement FastAPI endpoints approximately like:

```text
POST /workbooks/upload
POST /workbooks/{workbook_id}/process

GET /runs/{run_id}
GET /runs/{run_id}/status

GET /workbooks/{workbook_id}
GET /workbooks/{workbook_id}/sheets

GET /workbooks/{workbook_id}/tables
GET /workbooks/{workbook_id}/formulas
GET /workbooks/{workbook_id}/graph

GET /regions/{region_id}

POST /regions/{region_id}/feedback
POST /regions/{region_id}/reprocess

GET /health
```

Long processing may initially run synchronously or with a simple local task mechanism.

Do not add Kafka, Celery, Redis or distributed orchestration in MVP.

---

# 28. Processing Stages

Implement explicit stages:

```text
UPLOADED
INSPECTING
DETECTING_REGIONS
EXTRACTING_TABLES
EXTRACTING_TEXT
EXTRACTING_VISUALS
PARSING_FORMULAS
BUILDING_GRAPH
AGENT_REVIEW
NORMALIZING
EMBEDDING
QUALITY_CHECK
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
```

Persist stage/status for observability.

---

# 29. Logging

Use structured Python logging.

Every log line should include where relevant:

```text
run_id
workbook_id
sheet_name
region_id
stage
```

Do not log entire workbook contents or huge cell dumps.

---

# 30. Security / Safety

Even though local:

- never execute macros
- never execute workbook-provided code
- never follow external links automatically
- never overwrite source workbook
- sanitize filenames
- validate uploaded file extension
- enforce configurable upload size limit
- treat workbook cell text as untrusted data
- prevent arbitrary paths in API arguments
- keep LM tool calls limited to predefined safe functions

---

# 31. Configuration

Create `.env.example`.

Suggested settings:

```env
APP_ENV=local

DATA_DIR=./data
UPLOAD_DIR=./data/uploads
OUTPUT_DIR=./data/outputs

MAX_UPLOAD_MB=100
REGION_AGENT_THRESHOLD=0.70
MAX_AGENT_STEPS=8

LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
LLM_MODEL=
VLM_MODEL=
EMBEDDING_MODEL=

ENABLE_AGENT=true
ENABLE_VLM=true
ENABLE_EMBEDDINGS=true
ENABLE_LIBREOFFICE_RENDER=true

DUCKDB_PATH=./data/excel_intelligence.duckdb
SQLITE_PATH=./data/runs.sqlite
LANCEDB_PATH=./data/lancedb
```

---

# 32. MVP Unsupported / Limited Features

Detect and report, but do not fully support:

- VBA execution
- macros
- Power Query execution
- Power Pivot / DAX model execution
- Excel add-ins
- arbitrary external data source refresh
- external workbook auto-fetch
- password-protected files
- full Excel formula engine compatibility
- perfect visual parity with Microsoft Excel

The system should not fail the entire workbook merely because one unsupported feature exists.

---

# 33. Sample Workbooks

Create test fixtures programmatically.

At minimum generate:

## fixture_simple.xlsx

- 2 sheets
- 1 native table
- basic formulas

## fixture_multi_region.xlsx

- title
- table
- narrative block
- second table
- merged cells

## fixture_cross_sheet.xlsx

- source sheet
- lookup sheet
- summary sheet
- cross-sheet formulas

## fixture_complex.xlsx

- 5+ sheets
- hidden lookup sheet
- formulas
- named ranges
- comments
- merged cells
- image if practical
- chart
- multiple logical regions

Do not rely exclusively on manually created fixtures.

---

# 34. Testing Requirements

Use `pytest`.

## Unit tests

Cover:

- workbook inspection
- sheet inventory
- table detection
- native table extraction
- inferred table extraction
- formula extraction
- cross-sheet references
- dependency graph creation
- hidden sheets
- merged cells
- comments
- region confidence
- output manifests

## Integration tests

Cover:

```text
upload -> process -> normalized outputs
```

and:

```text
low-confidence region -> agent call -> normalized result
```

Mock LM Studio for CI tests.

Agent tests must not require a live model.

---

# 35. Acceptance Criteria

MVP is complete when all of the following work locally:

1. User can upload an `.xlsx` file in Streamlit.
2. Workbook run is registered.
3. All sheets are discovered.
4. Hidden sheets are identified.
5. Native Excel tables are extracted to Parquet.
6. Reasonable inferred table regions can be detected.
7. Narrative/text regions are captured.
8. Formula expressions are preserved.
9. Cross-sheet formula references are extracted.
10. Dependency graph is generated.
11. Embedded images are extracted where supported.
12. Charts are at least inventoried.
13. Low-confidence regions can be identified.
14. A low-confidence region can be sent to the LM Studio-backed agent.
15. Agent uses workbook tools rather than receiving the entire workbook.
16. User can submit feedback and reprocess one region.
17. Workbook outputs are stored under a run-specific output directory.
18. DuckDB contains normalized metadata.
19. Application still processes deterministically if LM Studio is offline.
20. Unit/integration tests pass.

---

# 36. Implementation Priority

Implement in this order.

## Phase 1 — Deterministic core

1. project scaffolding
2. settings
3. upload
4. run metadata
5. workbook inspection
6. sheet inventory
7. native table extraction
8. formula extraction
9. dependency graph
10. output manifest

Do not start agent work before these are stable.

## Phase 2 — Workbook structure

11. logical region detector
12. inferred table extraction
13. text extraction
14. comments
15. images/charts inventory
16. quality scoring

## Phase 3 — Local UI

17. Streamlit upload page
18. results page
19. review page

## Phase 4 — Agentic exceptions

20. LM Studio client
21. LangGraph agent
22. workbook tools
23. low-confidence escalation
24. optional VLM rendering
25. region remediation

## Phase 5 — Retrieval assets

26. summaries
27. embeddings
28. LanceDB

---

# 37. Engineering Principles

Follow these rules throughout implementation.

### Deterministic before probabilistic

If information is available directly from OOXML/openpyxl, do not ask the LLM for it.

### Region-level AI

Never send the full workbook to the LLM by default.

### Preserve provenance

Every extracted asset must retain workbook/sheet/range lineage.

### Fail partially

A failed chart or agent call must not discard successfully extracted tables/formulas.

### Local-first

The complete MVP must work without cloud infrastructure.

### Replaceable components

Keep interfaces around:

```text
LLM
vector store
structured store
graph store
rendering engine
```

so they can later map to Databricks/Azure.

### No premature distributed architecture

Do not add message queues, Kubernetes, Spark, Databricks or cloud services to the local MVP.

---

# 38. Future Enterprise Mapping

Design interfaces so the following migration remains straightforward:

```text
Local Prototype              Enterprise Target

Filesystem              ->   ADLS / Unity Catalog Volume
Python orchestrator      ->   Databricks Workflows / Lakeflow
DuckDB + Parquet         ->   Delta Lake
LanceDB                  ->   Mosaic AI Vector Search
NetworkX                 ->   Delta graph assets / graph store
LM Studio                ->   Databricks Model Serving / enterprise LLM
LangGraph                ->   enterprise agent runtime
Streamlit                ->   enterprise React/API UI if required
SQLite                   ->   Delta control tables
```

The following code should be reusable with minimal changes:

- workbook inspection
- region detection
- table extraction
- formula parser
- dependency graph logic
- normalized schemas
- agent tools
- quality checks
- tests

---

# 39. Definition of Done for Each Feature

A feature is not complete unless it has:

1. implementation
2. typed interfaces
3. error handling
4. structured logging
5. unit tests
6. integration into pipeline
7. output persisted
8. README usage notes where necessary

---

# 40. First Codex Task

Start by implementing only **Phase 1 — Deterministic Core**.

Deliver:

- repository scaffolding
- `pyproject.toml`
- `.env.example`
- settings
- Pydantic models
- workbook upload/storage
- run registry
- workbook inspector
- sheet inventory
- native Excel table extractor
- formula extractor
- initial cross-sheet dependency parser
- NetworkX graph builder
- JSON/Parquet/DuckDB outputs
- sample workbook generator
- pytest tests
- basic FastAPI health/run endpoints

After Phase 1 passes tests, proceed to later phases.

Do not implement the LangGraph agent in the first coding pass.
