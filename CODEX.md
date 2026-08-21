# Workbook Agent — Codex Implementation Specification

## 1. Purpose of this file

This file is the implementation contract for Codex. Build a working local-first web application that allows a user to:

1. Upload an Excel workbook.
2. Let the system inspect and understand its structure, formulas, relationships, images, charts, and business context.
3. Produce a normalized **Workbook Knowledge Package** suitable for embeddings, entity extraction, relationship extraction, knowledge-graph construction, RAG, and downstream analytics.
4. Review low-confidence findings.
5. Give natural-language or structured feedback.
6. Reprocess only the impacted parts of the workbook while preserving approved outputs.
7. Inspect previous workbooks and processing runs.

The initial application must run locally and use models served through **LM Studio**. The architecture must keep model providers and agent frameworks replaceable.

---

## 2. Product name and language

**User-facing product name:** Workbook Agent  
**Processing capability name:** Workbook Intelligence Agent  
**Primary action label:** Analyze Workbook

Use business-friendly language in the UI. Do not expose internal terms such as chain-of-thought, prompt loop, LangChain graph, or subagent unless the user opens a technical details panel.

---

## 3. Product principles

1. **Simple UI, complex backend.** Keep orchestration and extraction complexity behind the interface.
2. **Deterministic extraction first.** Use parsers and rules to establish facts. Use LLMs/VLMs for interpretation, ambiguity resolution, summarization, semantic mapping, and planning.
3. **Never flatten the workbook prematurely.** Preserve workbook, sheet, region, table, formula, image, chart, relationship, and provenance information.
4. **Normalized outputs are the product.** The output is not merely CSV or extracted text; it is a canonical knowledge package.
5. **Feedback is executable.** Convert user feedback into structured processing directives and store it with the run.
6. **Incremental reprocessing.** Reprocess only impacted assets unless the user explicitly selects the full workbook.
7. **Traceability.** Every generated chunk, entity, relationship, or summary must point back to the workbook, sheet, cell/range, image, chart, query, or formula from which it came.
8. **Local-first and private.** Do not send workbook content to an external service by default.
9. **Safe processing.** Detect macros and embedded code but do not execute them.
10. **Framework portability.** Keep the domain pipeline independent from LangChain Deep Agents or Google ADK.

---

## 4. Design references

The user will provide application screenshots. Treat the screenshots as the visual source of truth.

Expected location:

```text
design_reference/
├── 01-home.png
├── 02-my-workbooks.png
├── 03-run-history.png
└── optional-additional-screens.png
```

Before implementing any UI screen:

1. Inspect all files in `design_reference/`.
2. Match layout, spacing, typography hierarchy, border radius, table density, status pills, icons, button sizes, and the green/white visual language.
3. Reuse one consistent shell and design system across all screens.
4. Do not add decorative dashboards, excessive KPI cards, charts, gradients, or technical panels not present in the screenshots.
5. The UI should feel spacious, calm, and enterprise-ready.
6. Use the screenshots for visual direction, but implement real responsive components rather than embedding screenshots.

### Visual style

- White and very light gray surfaces.
- Excel-inspired green as the primary action color.
- Soft green selected-navigation background.
- Thin neutral borders.
- Minimal shadows.
- Rounded cards, inputs, and table containers.
- Dark navy/charcoal text, muted gray secondary text.
- Avoid heavy blue styling from earlier concepts.
- Desktop-first, responsive down to tablet width.

---

## 5. Scope

### 5.1 MVP scope

Support:

- `.xlsx`
- `.xlsm` with macro detection and static inspection only
- `.xlsb` on a best-effort basis
- Multiple sheets
- Hidden and very hidden sheets where discoverable
- Multiple tables or regions per sheet
- Multi-row and merged headers
- Repeated blocks
- Forms and label-value layouts
- Cross-sheet formulas
- Named ranges
- Structured table references
- Lookup relationships
- Basic external-link and workbook-connection detection
- Embedded images and screenshots
- Chart metadata and chart summaries
- Comments and notes
- Conditional-formatting metadata where accessible
- Normalized datasets
- Semantic content units
- Formula and lineage assets
- Entity and relationship candidates
- Embedding-ready chunks
- Review queue
- Natural-language feedback
- Incremental reprocessing
- Run history and run comparison
- Downloadable output package

### 5.2 Explicit non-goals for the first release

Do not attempt to:

- Execute VBA or Office Scripts.
- Reproduce the full Microsoft Excel calculation engine.
- Crack passwords or bypass workbook protection.
- Support every proprietary add-in.
- Guarantee refresh of inaccessible external systems.
- Convert every chart image into exact underlying data.
- Build a full graph visualization product.
- Build a full vector database administration UI.
- Build role-based access control beyond a simple local user mode.
- Add cloud deployment integrations unless the core local workflow is complete.

---

## 6. Recommended technical stack

### 6.1 Frontend

Use:

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Zustand only for small client-side UI state
- React Hook Form
- Zod
- Tailwind CSS
- shadcn/ui primitives where useful
- Lucide React icons
- Native EventSource for Server-Sent Events
- Vitest and React Testing Library
- Playwright for end-to-end tests

Do not use a large state-management framework. Server state belongs in TanStack Query.

### 6.2 Backend

Use:

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x or SQLModel
- Alembic
- SQLite for local development
- PostgreSQL-compatible schema for later deployment
- Redis + RQ for background processing jobs
- Server-Sent Events for progress updates
- `structlog` or standard structured JSON logging
- `pytest`, `pytest-asyncio`, and `httpx`

Do not run long workbook processing directly in the API request process.

### 6.3 Workbook and document processing libraries

Use a modular adapter layer. Candidate open-source libraries:

- `openpyxl` for `.xlsx` and `.xlsm` workbook structure, formulas, styles, tables, charts, comments, and images where supported
- `pyxlsb` for `.xlsb`
- `xlrd` only for legacy `.xls` if later enabled
- `pandas` or `polars` for tabular normalization
- `pyarrow` for Parquet output
- Python `zipfile` and `lxml` for direct OOXML package inspection when a high-level library does not expose workbook relationships
- `oletools` for static macro inspection
- `msoffcrypto-tool` only to detect or open a workbook when a password is explicitly supplied by the user; never attempt password recovery
- `Pillow` for image handling
- Optional `PaddleOCR` or `Tesseract` adapter for text-heavy images
- Optional `img2table` adapter for scanned table extraction
- `networkx` for in-memory dependency graphs and graph algorithms

Keep every parser behind an interface so a library can be replaced without changing the domain model.

### 6.4 LLM, VLM, and embeddings

Default local endpoint:

```text
http://localhost:1234/v1
```

Use an OpenAI-compatible client adapter so LM Studio models can be configured by environment variables.

Required model roles:

- `reasoning_model`: workbook planning, semantic interpretation, feedback interpretation, validation summaries
- `vision_model`: screenshots, images, pasted charts, scanned forms, and diagram interpretation
- `embedding_model`: semantic content-unit embeddings

Do not hard-code model names. Discover available models and allow configuration through environment variables and a small settings file.

### 6.5 Agent framework

Use **LangChain Deep Agents** for the first implementation, behind an internal `AgentRuntime` interface.

Reasons for this implementation choice:

- The workflow needs planning and tool invocation.
- Specialist tasks can be delegated without embedding orchestration logic in API routes.
- The model provider remains configurable.

Create a second empty adapter boundary for **Google ADK**. Do not implement both frameworks at the same time in the MVP.

The domain services and deterministic tools must not import Deep Agents directly. Only `infrastructure/agents/deepagents_runtime.py` should depend on the framework.

---

## 7. High-level architecture

```text
React Web App
     │
     │ REST + SSE
     ▼
FastAPI API
     │
     ├── Workbook service
     ├── Run service
     ├── Review and feedback service
     ├── Asset service
     └── Model configuration service
             │
             ▼
       Redis / RQ Worker
             │
             ▼
   Workbook Processing Orchestrator
             │
     ┌───────┼───────────────────────────────┐
     │       │                               │
     ▼       ▼                               ▼
Deterministic extraction tools      Agent runtime        Validation engine
     │                               │                    │
     ├── workbook profiler           ├── supervisor       ├── reconciliation
     ├── region detector             ├── structure agent  ├── schema checks
     ├── table normalizer            ├── semantic agent   ├── lineage checks
     ├── formula parser              ├── visual agent     └── confidence scoring
     ├── image extractor             └── validation agent
     ├── chart extractor
     ├── connection inspector
     └── package writer
             │
             ▼
   Canonical Workbook Knowledge Package
             │
     ┌───────┼────────────┬──────────────┐
     ▼       ▼            ▼              ▼
 JSONL    Parquet       Images        Nodes/Edges
```

---

## 8. Repository structure

Create a monorepo with this structure:

```text
workbook-agent/
├── CODEX.md
├── README.md
├── .env.example
├── docker-compose.yml
├── Makefile
├── design_reference/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── App.tsx
│   │   │   ├── router.tsx
│   │   │   └── providers.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   ├── common/
│   │   │   ├── workbooks/
│   │   │   ├── runs/
│   │   │   ├── assets/
│   │   │   └── review/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── WorkbooksPage.tsx
│   │   │   ├── WorkbookDetailPage.tsx
│   │   │   ├── RunHistoryPage.tsx
│   │   │   ├── RunDetailPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── api/
│   │   ├── hooks/
│   │   ├── types/
│   │   ├── utils/
│   │   └── styles/
│   └── tests/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   ├── errors.py
│   │   │   └── security.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── workbooks.py
│   │   │       ├── runs.py
│   │   │       ├── assets.py
│   │   │       ├── reviews.py
│   │   │       └── models.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   ├── models/
│   │   │   └── migrations/
│   │   ├── domain/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── enums.py
│   │   │   └── protocols.py
│   │   ├── services/
│   │   │   ├── workbook_service.py
│   │   │   ├── run_service.py
│   │   │   ├── feedback_service.py
│   │   │   ├── asset_service.py
│   │   │   ├── review_service.py
│   │   │   └── package_service.py
│   │   ├── processing/
│   │   │   ├── orchestrator.py
│   │   │   ├── stages.py
│   │   │   ├── context.py
│   │   │   ├── directives.py
│   │   │   ├── confidence.py
│   │   │   ├── extractors/
│   │   │   ├── normalizers/
│   │   │   ├── analyzers/
│   │   │   ├── validators/
│   │   │   └── package_writer/
│   │   ├── agents/
│   │   │   ├── runtime.py
│   │   │   ├── supervisor.py
│   │   │   ├── prompts/
│   │   │   ├── tools/
│   │   │   └── deepagents_runtime.py
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   ├── model_registry.py
│   │   │   ├── structured_output.py
│   │   │   ├── vision.py
│   │   │   └── embeddings.py
│   │   ├── jobs/
│   │   │   ├── queue.py
│   │   │   └── tasks.py
│   │   └── storage/
│   │       ├── object_store.py
│   │       ├── local_store.py
│   │       └── paths.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── fixtures/
│       └── golden/
└── scripts/
    ├── seed_demo.py
    ├── create_test_workbooks.py
    └── verify_lmstudio.py
```

---

## 9. Core domain entities

### 9.1 Workbook

Fields:

- `id`
- `original_filename`
- `display_name`
- `file_type`
- `file_size_bytes`
- `sha256`
- `storage_uri`
- `purpose`
- `description`
- `created_at`
- `updated_at`
- `latest_run_id`
- `latest_status`
- `latest_confidence`
- `is_archived`

A workbook appears once in **My Workbooks**, regardless of the number of runs.

### 9.2 ProcessingRun

Fields:

- `id`
- `workbook_id`
- `parent_run_id`
- `run_number`
- `trigger_type`: `initial`, `manual_rerun`, `feedback_rerun`, `retry`
- `scope`: `full_workbook`, `selected_sheets`, `selected_assets`, `impacted_assets`
- `status`: `queued`, `profiling`, `planning`, `extracting`, `interpreting`, `validating`, `packaging`, `needs_review`, `completed`, `failed`, `cancelled`
- `current_stage`
- `progress_percent`
- `started_at`
- `completed_at`
- `duration_seconds`
- `overall_confidence`
- `output_unit_count`
- `error_code`
- `error_message`
- `accepted_at`

Each run appears separately in **Run History**.

### 9.3 Feedback

Fields:

- `id`
- `run_id`
- `workbook_id`
- `raw_text`
- `feedback_type`
- `scope_type`
- `scope_ids`
- `created_at`
- `created_by`
- `parsed_directives`
- `parse_confidence`
- `status`: `draft`, `parsed`, `approved`, `applied`, `rejected`

### 9.4 ProcessingDirective

Use a typed discriminated union. Initial directive types:

- `override_header_row`
- `ignore_rows`
- `ignore_columns`
- `exclude_sheet`
- `include_hidden_sheet`
- `rename_table`
- `rename_column`
- `confirm_semantic_mapping`
- `reject_semantic_mapping`
- `confirm_relationship`
- `reject_relationship`
- `set_sheet_role`
- `set_region_type`
- `exclude_visual_asset`
- `correct_visual_interpretation`
- `set_business_context`
- `set_unit_or_currency`
- `preserve_approved_assets`
- `force_reprocess_asset`

Every directive must contain:

- `directive_id`
- `type`
- `target`
- `parameters`
- `source_feedback_id`
- `confidence`
- `requires_confirmation`

### 9.5 Asset

Store a lightweight asset index in the database and the complete content in object storage.

Fields:

- `id`
- `run_id`
- `workbook_id`
- `parent_asset_id`
- `asset_type`
- `title`
- `summary`
- `source_uri`
- `content_uri`
- `preview_uri`
- `source_sheet`
- `source_range`
- `confidence`
- `review_status`
- `is_approved`
- `created_at`

Asset types:

- `workbook_manifest`
- `workbook_summary`
- `sheet`
- `region`
- `table`
- `column`
- `record`
- `form_record`
- `formula`
- `business_rule`
- `named_range`
- `query`
- `connection`
- `image`
- `chart`
- `comment`
- `semantic_unit`
- `embedding_chunk`
- `entity`
- `relationship`
- `lineage_edge`
- `quality_issue`
- `review_item`

### 9.6 ReviewItem

Fields:

- `id`
- `run_id`
- `asset_id`
- `review_type`
- `title`
- `description`
- `evidence`
- `suggested_action`
- `confidence`
- `severity`
- `status`: `open`, `confirmed`, `corrected`, `rejected`, `ignored`
- `resolution`
- `resolved_at`

---

## 10. Canonical Workbook Knowledge Package

Each completed run must create this package:

```text
storage/workbooks/{workbook_id}/runs/{run_id}/package/
├── manifest.json
├── workbook_summary.json
├── metadata/
│   ├── sheets.jsonl
│   ├── regions.jsonl
│   ├── tables.jsonl
│   ├── columns.jsonl
│   ├── formulas.jsonl
│   ├── named_ranges.jsonl
│   ├── queries.jsonl
│   ├── connections.jsonl
│   ├── charts.jsonl
│   └── images.jsonl
├── structured_data/
│   ├── {normalized_table_id}.parquet
│   └── ...
├── semantic_units/
│   ├── workbook_units.jsonl
│   ├── sheet_units.jsonl
│   ├── table_units.jsonl
│   ├── record_units.jsonl
│   ├── formula_units.jsonl
│   └── visual_units.jsonl
├── graph/
│   ├── nodes.jsonl
│   └── edges.jsonl
├── media/
│   ├── images/
│   └── embedded_files/
├── embedding_input/
│   └── chunks.jsonl
├── quality/
│   ├── validation_report.json
│   ├── issues.jsonl
│   └── review_items.jsonl
└── lineage/
    ├── technical_lineage.jsonl
    └── business_lineage.jsonl
```

### 10.1 Canonical content unit

Implement this as a Pydantic model:

```json
{
  "unit_id": "wb_001.sheet_03.table_02.row_015",
  "unit_type": "table_record",
  "title": "Equipment inspection record EQ-2034",
  "text_content": "Equipment EQ-2034 was inspected on 14 August 2026. A crack was observed near the inlet valve. The status is Requires Maintenance.",
  "structured_content": {
    "equipment_id": "EQ-2034",
    "inspection_date": "2026-08-14",
    "observation": "Crack near inlet valve",
    "status": "Requires Maintenance"
  },
  "semantic_context": {
    "domain": "Equipment Maintenance",
    "entity_type": "Equipment Inspection",
    "business_terms": ["Equipment", "Inspection", "Maintenance Status"]
  },
  "structural_context": {
    "workbook_id": "wb_001",
    "sheet_id": "sheet_03",
    "sheet_name": "Inspection",
    "region_id": "region_04",
    "table_id": "table_02",
    "row_number": 15
  },
  "media_references": ["wb_001.sheet_03.image_008"],
  "relationships": [
    {
      "type": "INSPECTION_OF",
      "target_id": "equipment.EQ-2034"
    }
  ],
  "provenance": {
    "source_file": "equipment_inspection.xlsx",
    "source_range": "A15:H15",
    "source_cells": ["A15", "B15", "C15", "D15", "E15", "F15", "G15", "H15"],
    "extraction_method": "table_parser",
    "processor_version": "0.1.0"
  },
  "quality": {
    "extraction_confidence": 0.98,
    "semantic_confidence": 0.91,
    "validation_status": "passed"
  },
  "embedding_status": "ready",
  "entity_extraction_status": "ready"
}
```

### 10.2 Embedding chunk

```json
{
  "chunk_id": "chunk.wb_001.sheet_03.table_02.row_015",
  "chunk_type": "table_record",
  "embedding_text": "For the East region and Consumer Electronics category, forecast revenue for August 2026 is INR 5.8 million based on a growth assumption of 7.5 percent.",
  "metadata": {
    "workbook_id": "wb_001",
    "run_id": "run_018",
    "sheet_name": "Regional Forecast",
    "table_name": "Regional Sales Forecast",
    "region": "East",
    "product_category": "Consumer Electronics",
    "forecast_month": "2026-08",
    "source_range": "A15:H15"
  },
  "source_unit_id": "wb_001.sheet_03.table_02.row_015"
}
```

Rules:

- Never embed isolated values without labels and context.
- Do not create one embedding per cell.
- Use workbook, sheet, table, record, formula, visual, and relationship-level semantic units.
- Include source metadata with every chunk.
- Keep derived insights clearly marked as derived.

### 10.3 Graph edge

```json
{
  "edge_id": "edge_00157",
  "source_id": "wb_001.sheet_03.table_02",
  "relationship_type": "DERIVED_FROM",
  "target_id": "wb_001.sheet_02.table_01",
  "relationship_description": "The regional forecast table is derived from historical sales data.",
  "evidence": ["formula_reference", "query_dependency"],
  "confidence": 0.97,
  "provenance": {
    "source_sheet": "Regional Forecast",
    "source_range": "H15:H200"
  }
}
```

---

## 11. Processing pipeline

Implement the pipeline as explicit, restartable stages. Each stage writes durable intermediate outputs and emits progress events.

### Stage 0: Intake and safety

- Validate extension and MIME signature.
- Calculate SHA-256.
- Copy original file to immutable object storage.
- Detect encryption/protection.
- Detect macros, embedded objects, and external links.
- Reject unsupported or unsafe content with a clear error.
- Never execute workbook code.

### Stage 1: Workbook profiling

Create a deterministic manifest containing:

- Workbook properties
- Sheet names and visibility
- Used ranges
- Tables
- Merged cells
- Formula counts
- Named ranges
- Comments/notes
- Charts
- Images/shapes
- Pivot metadata where accessible
- Query/connection metadata where accessible
- External workbook references
- Macro presence
- Protection state

### Stage 2: Complexity classification

Score independently:

- Layout complexity
- Data complexity
- Dependency complexity
- Computation complexity
- Connectivity complexity
- Visual complexity
- Semantic complexity
- Automation complexity

Also infer one or more workbook archetypes:

- flat dataset
- multi-table data package
- human-readable report
- analytical model
- BI workbook
- operational application

The agent can help interpret the profile, but the score must include deterministic evidence.

### Stage 3: Processing plan

The supervisor creates a structured plan that selects only the required tools. Store the plan as JSON.

Example:

```json
{
  "workbook_archetype": "analytical_model",
  "steps": [
    "detect_regions",
    "extract_tables",
    "parse_formula_dependencies",
    "classify_input_calculation_output_sheets",
    "process_visual_assets",
    "generate_semantic_units",
    "validate_reconciliations"
  ],
  "excluded_steps": ["full_macro_analysis"],
  "reasoning_summary": "The workbook contains multiple calculation sheets, cross-sheet formulas, assumptions, and a dashboard."
}
```

Do not store hidden chain-of-thought. Store only a concise decision summary and evidence.

### Stage 4: Sheet and region understanding

Detect and classify regions:

- table
- repeated block
- form
- label-value area
- summary
- lookup/reference
- assumptions/input
- calculation
- chart-source area
- dashboard
- notes
- decorative area

Persist coordinates and confidence.

### Stage 5: Structured extraction and normalization

- Detect headers and multi-row headers.
- Normalize column names while preserving originals.
- Infer data types.
- Preserve units, currencies, and date semantics.
- Separate transaction rows from subtotals and notes.
- Normalize repeated blocks.
- Unpivot matrices when appropriate.
- Generate Parquet outputs.
- Generate row-level provenance maps.

### Stage 6: Formula and dependency analysis

Create:

- Cell-to-cell dependencies
- Range dependencies
- Cross-sheet dependencies
- Named-range dependencies
- Table-reference dependencies
- Lookup-based join candidates
- External-workbook dependencies
- Formula pattern groups
- Formula inconsistencies and hard-coded overrides
- Circular-reference indicators
- Broken-reference indicators

Convert formulas into:

- Original Excel expression
- Normalized expression
- Natural-language business-rule text
- Inputs
- Output
- Formula category
- Technical lineage
- Business lineage candidate

Do not claim that formula values were recalculated unless an actual supported calculation engine performed the calculation.

### Stage 7: Visual and multimodal processing

For every image or visual object:

1. Extract the binary asset.
2. Record sheet, anchor cell, coordinates, and nearby context.
3. Deduplicate by perceptual or binary hash.
4. Classify as decorative, screenshot, scanned table, photograph, chart image, process diagram, signature/stamp, document excerpt, or unknown.
5. Route to OCR, table extraction, or VLM only when useful.
6. Generate a concise description.
7. Associate the visual with the nearest relevant record, region, table, form field, or dashboard element.
8. Create review items for low-confidence interpretations.

Decorative logos should not become embedding chunks by default.

### Stage 8: Semantic asset generation

Generate:

- Workbook summary
- Sheet summaries
- Region summaries
- Table descriptions
- Column descriptions
- Record-level semantic text where valuable
- Formula and rule descriptions
- Image descriptions
- Chart summaries
- Comment/note units
- Business terms
- Entity candidates
- Relationship candidates

The LLM must return validated structured JSON matching Pydantic schemas.

### Stage 9: Validation and reconciliation

Run deterministic checks:

- Extracted row counts
- Header/data consistency
- Data type consistency
- Duplicate records
- Formula pattern anomalies
- Broken references
- Missing external sources
- Reconstructed totals where feasible
- Source-to-normalized traceability
- Every semantic unit has provenance
- Every graph edge has evidence
- Every image has a source location

Create component-level confidence scores rather than one opaque score.

### Stage 10: Review queue

Create review items only when action is useful. Examples:

- uncertain header row
- probable cross-sheet key mapping
- ambiguous blank-value interpretation
- possible table boundary
- uncertain image interpretation
- missing external dependency
- conflicting metric definitions
- suspected hard-coded override

### Stage 11: Package creation

Write the complete package, index its assets, generate a ZIP download, and mark the run completed or needs review.

---

## 12. Agent design

### 12.1 Core rule

The agent does not directly manipulate files or databases. It calls typed tools. Tools perform deterministic actions and return structured results.

### 12.2 Supervisor agent

Responsibilities:

- Read the workbook profile.
- Select the processing path.
- Call specialist tools.
- Request specialist semantic interpretation only where needed.
- Track unresolved issues.
- Trigger validation.
- Produce a concise completion summary.

The supervisor must not:

- Execute arbitrary code.
- Execute workbook macros.
- Modify the original workbook.
- Invent worksheet content.
- Mark an output as validated without evidence.

### 12.3 Specialist capabilities

Implement these initially as tools plus focused prompts. They may become subagents later.

1. **Structure interpreter**
   - Determines sheet roles and region meanings from deterministic profile evidence.

2. **Formula and lineage interpreter**
   - Converts formula graphs into understandable rules and business lineage.

3. **Visual interpreter**
   - Describes and classifies image assets using the VLM.

4. **Semantic mapper**
   - Maps fields and assets to business concepts and finds entity/relationship candidates.

5. **Validation reviewer**
   - Summarizes deterministic validation failures and recommends review actions.

6. **Feedback interpreter**
   - Converts user feedback into typed processing directives.

### 12.4 Required tool contracts

Create typed tools for:

- `get_workbook_manifest`
- `get_sheet_profile`
- `detect_sheet_regions`
- `extract_region_table`
- `normalize_table`
- `get_formula_graph`
- `get_formula_pattern_anomalies`
- `get_named_ranges`
- `get_external_dependencies`
- `get_visual_assets`
- `describe_visual_asset`
- `generate_semantic_units`
- `infer_entity_candidates`
- `infer_relationship_candidates`
- `validate_assets`
- `create_review_item`
- `get_previous_run_feedback`
- `apply_processing_directives`
- `calculate_impacted_assets`
- `write_knowledge_package`

Each tool must:

- Validate input with Pydantic.
- Return structured output.
- Log duration and status.
- Be idempotent for the same run and input hash.
- Store large results in object storage and return references.

### 12.5 Local-model reliability controls

Local models may vary in tool-calling and structured-output quality. Implement:

- JSON schema validation
- Automatic repair attempt with strict retry limit
- Maximum agent steps
- Maximum retries per tool
- Timeouts
- Model capability check
- Fallback structured planning prompt when native tool calls fail
- Deterministic default processing path if the agent is unavailable
- No infinite planning or self-reflection loop

The application must still create a partial deterministic package when the LLM is unavailable. Mark semantic stages as incomplete and show a clear status.

---

## 13. Feedback-driven reprocessing

### 13.1 User experience

The user can click **Reprocess** from a workbook or run.

Show a right-side drawer with:

- Free-text feedback
- Apply to: entire workbook, selected sheets, selected assets, impacted assets
- Sheet/asset selectors when relevant
- Preserve confirmed entities and mappings
- Preserve approved table structures
- Reprocess only impacted assets
- Start Reprocessing

### 13.2 Feedback interpretation flow

```text
User feedback
    ↓
Feedback interpreter
    ↓
Typed directives
    ↓
User confirmation when directive is ambiguous or destructive
    ↓
Impact analysis
    ↓
New child run
    ↓
Reuse unaffected approved assets
    ↓
Reprocess impacted stages
    ↓
Validate
    ↓
Compare runs
```

Example feedback:

```text
The first two rows in Forecast are titles. Treat row 3 as the header. Customer No and Account ID are the same identifier.
```

Parsed directives:

```json
[
  {
    "type": "override_header_row",
    "target": {"sheet_name": "Forecast"},
    "parameters": {"header_row": 3, "ignore_rows": [1, 2]},
    "requires_confirmation": false
  },
  {
    "type": "confirm_semantic_mapping",
    "target": {
      "source_field": "Orders.Customer No",
      "target_field": "Customer Master.Account ID"
    },
    "parameters": {"enterprise_term": "Customer Identifier"},
    "requires_confirmation": false
  }
]
```

### 13.3 Impact analysis

Maintain an asset dependency graph. A directive should identify impacted assets.

Example:

```text
Header override on Forecast sheet
  → Forecast table schema
  → Forecast records
  → Formula references using that table
  → Formula semantic units
  → Related entities and relationships
  → Embedding chunks
  → Validation report
```

Do not automatically invalidate unrelated sheets or images.

### 13.4 Run comparison

Compare:

- Tables added, changed, removed
- Record counts
- Semantic units
- Entities
- Relationships
- Rules
- Review items
- Confidence
- Applied directives

Allow the user to accept a run as the current version.

---

## 14. API specification

Use `/api/v1` prefix.

### 14.1 Health and model configuration

```text
GET  /api/v1/health
GET  /api/v1/models/status
GET  /api/v1/models
PUT  /api/v1/models/config
```

Model status must show:

- LM Studio reachable
- Available model identifiers
- Configured reasoning model
- Configured vision model
- Configured embedding model
- Basic capability check result

### 14.2 Workbooks

```text
POST   /api/v1/workbooks
GET    /api/v1/workbooks
GET    /api/v1/workbooks/{workbook_id}
PATCH  /api/v1/workbooks/{workbook_id}
DELETE /api/v1/workbooks/{workbook_id}
POST   /api/v1/workbooks/{workbook_id}/runs
```

Upload uses multipart form data:

- `file`
- `purpose`
- `description`

Support pagination, search, and filters.

### 14.3 Runs

```text
GET  /api/v1/runs
GET  /api/v1/runs/{run_id}
GET  /api/v1/runs/{run_id}/events
POST /api/v1/runs/{run_id}/cancel
POST /api/v1/runs/{run_id}/retry
POST /api/v1/runs/{run_id}/accept
GET  /api/v1/runs/{run_id}/compare/{other_run_id}
```

`/events` uses Server-Sent Events.

Event structure:

```json
{
  "event_id": "evt_001",
  "run_id": "run_018",
  "timestamp": "2026-08-21T10:32:00Z",
  "stage": "formula_analysis",
  "status": "in_progress",
  "progress_percent": 46,
  "message": "Analyzing formulas and cross-sheet dependencies",
  "details": {
    "formulas_processed": 1240,
    "formulas_total": 2418
  }
}
```

### 14.4 Assets

```text
GET /api/v1/runs/{run_id}/assets
GET /api/v1/assets/{asset_id}
GET /api/v1/assets/{asset_id}/preview
GET /api/v1/assets/{asset_id}/download
GET /api/v1/runs/{run_id}/package/download
```

Filters:

- asset type
- sheet
- review status
- confidence range
- search

### 14.5 Review

```text
GET  /api/v1/runs/{run_id}/review-items
POST /api/v1/review-items/{review_item_id}/confirm
POST /api/v1/review-items/{review_item_id}/correct
POST /api/v1/review-items/{review_item_id}/reject
POST /api/v1/review-items/{review_item_id}/ignore
```

### 14.6 Feedback and reprocessing

```text
POST /api/v1/runs/{run_id}/feedback/parse
POST /api/v1/runs/{run_id}/reprocess
GET  /api/v1/runs/{run_id}/directives
```

The parse endpoint returns proposed directives before starting a run when confirmation is required.

---

## 15. UI pages

### 15.1 Shared application shell

Left navigation:

- Home
- My Workbooks
- Run History

Bottom utility links:

- Feedback
- Settings

Header:

- Workbook Agent logo/name
- Help icon
- User avatar or initials

Do not add a large global header or complex mega-navigation.

### 15.2 Home

Match `01-home.png`.

Main content:

- Title: `Process your Excel workbook`
- Short explanation
- Large drag-and-drop upload area
- Supported-format text
- Browse Files button
- Purpose dropdown
- Optional description
- Analyze Workbook button
- Recent Workbooks table
- Small four-step “How it works” strip

Upload interaction:

1. Drop or browse a file.
2. Display file name, size, and remove action.
3. Purpose defaults to `Knowledge extraction / Entity & relationship`.
4. User clicks Analyze Workbook.
5. Create workbook and initial run.
6. Navigate to run detail/processing state.

### 15.3 My Workbooks

Match `02-my-workbooks.png`.

Purpose: permanent workbook library.

Show:

- Search
- Filters: All, Completed, Needs Review, Processing, Failed
- Upload Workbook button
- Minimal summary cards only if present in the screenshot
- Workbook table

Columns:

- Workbook
- Purpose
- Last Run
- Status
- Confidence
- Actions

Each workbook appears once. Clicking a row opens the workbook detail.

Actions menu:

- Open
- Reprocess
- Download latest package
- View runs
- Archive

### 15.4 Run History

Match `03-run-history.png`.

Purpose: audit trail of processing attempts.

Show:

- Search
- Status filters
- Sort dropdown
- Minimal run summary
- Recent Runs table
- Selected-run side panel on desktop

Columns:

- Run ID
- Workbook
- Started
- Duration
- Status
- Output
- Actions

Selected-run panel:

- Run ID
- Workbook
- Purpose
- Trigger
- Status
- Confidence
- Output count
- Feedback summary when applicable
- View Output button
- Re-run button

### 15.5 Workbook detail

Keep this screen simpler than the earlier heavy dashboard concept.

Header:

- Workbook name
- Latest status
- Confidence
- Last processed time
- Download Package
- Reprocess

Tabs:

- Overview
- Output Assets
- Review
- Runs

#### Overview

Show only:

- Plain-language workbook understanding
- Workbook type and purpose
- Key structural facts
- Simple inferred flow such as `Source Data → Assumptions → Forecast → Dashboard`
- Current run status
- Primary unresolved issues

Do not use more than four small metric cards.

#### Output Assets

Use grouped, collapsible sections:

- Normalized datasets
- Semantic and embedding units
- Entities and relationships
- Formula and lineage assets
- Visual assets
- Quality report

Each item has Preview and Download actions.

#### Review

List open review items as simple cards with evidence and actions.

#### Runs

List all runs for this workbook and support comparison.

### 15.6 Processing state

Show a clean vertical stage list, not an architecture diagram.

Example:

```text
✓ Workbook inspected
✓ Sheets and regions identified
● Analyzing formulas and relationships
○ Processing images and charts
○ Creating normalized knowledge assets
○ Validating outputs
```

Show current stage, short activity text, progress bar, cancel action, and optional technical log drawer.

### 15.7 Reprocess drawer

Fields:

- Feedback textarea
- Apply feedback to
- Sheet or asset selector
- Preserve confirmed mappings
- Preserve approved structures
- Reprocess only impacted assets
- Start Reprocessing

After parsing feedback, show the interpreted directives in plain language when confirmation is required.

---

## 16. State and interaction rules

- Every async action must show loading, success, and error states.
- Tables must support empty states.
- Upload must display validation errors clearly.
- Processing progress must recover after page refresh by reconnecting to SSE and fetching run state.
- No optimistic success for processing or review actions.
- Review actions should invalidate relevant TanStack Query caches.
- Use accessible labels and keyboard focus states.
- Use status pill colors consistently:
  - completed: green
  - needs review: amber
  - processing: blue or neutral active
  - failed: red
  - queued: gray
- Avoid modals for long feedback forms; use a side drawer.

---

## 17. LM Studio integration

### 17.1 Environment variables

Create `.env.example`:

```bash
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=sqlite:///./data/workbook_agent.db
REDIS_URL=redis://localhost:6379/0
STORAGE_ROOT=./data/storage
MAX_UPLOAD_MB=200

AGENT_FRAMEWORK=deepagents
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
LLM_REASONING_MODEL=
LLM_VISION_MODEL=
EMBEDDING_MODEL=
LLM_TEMPERATURE=0.1
LLM_REQUEST_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=2
AGENT_MAX_STEPS=20

ENABLE_OCR=true
OCR_PROVIDER=paddleocr
ENABLE_VISION=true
ENABLE_EMBEDDINGS=true
ENABLE_ENTITY_EXTRACTION=true
ENABLE_GRAPH_ASSETS=true
```

When running the backend inside Docker on macOS or Windows, document the use of:

```text
http://host.docker.internal:1234/v1
```

### 17.2 Model registry

At startup:

1. Call the model-list endpoint.
2. Validate configured model names.
3. Store a capability snapshot.
4. Expose status through the API.
5. Do not fail the entire backend if LM Studio is offline.

### 17.3 Structured output

All LLM responses used by the pipeline must be parsed into Pydantic models.

Implement:

- schema-first prompts
- strict JSON extraction
- one repair attempt
- fallback error object
- raw-response storage for debugging, with workbook-sensitive logs disabled by default

### 17.4 Vision prompts

Send:

- cropped image or embedded image
- sheet name
- anchor range
- nearest headers and row context
- requested classification schema

Do not send the entire workbook context with every image.

### 17.5 Embedding abstraction

Create an `EmbeddingProvider` protocol.

Implement:

- `LMStudioEmbeddingProvider`
- optional `SentenceTransformersEmbeddingProvider`
- `NoOpEmbeddingProvider` for tests

Store embeddings outside the main relational database. For MVP, write vectors to a local file or a small local vector store only after canonical chunks are created. The package must remain usable without a vector database.

---

## 18. Storage and privacy

### 18.1 Local object storage

Use a filesystem implementation with an interface compatible with later S3 storage.

Paths:

```text
data/storage/workbooks/{workbook_id}/original/{filename}
data/storage/workbooks/{workbook_id}/runs/{run_id}/intermediate/
data/storage/workbooks/{workbook_id}/runs/{run_id}/package/
data/storage/workbooks/{workbook_id}/runs/{run_id}/logs/
```

### 18.2 Privacy

- Do not log cell values or image text by default.
- Log asset IDs, counts, ranges, stage names, durations, and errors.
- Provide a development-only flag for detailed diagnostic logs.
- Never send data outside LM Studio/local services unless a future connector is explicitly configured.

### 18.3 Safety

- Static-inspect macros; never execute them.
- Sanitize filenames.
- Prevent path traversal.
- Enforce file-size limits.
- Store uploads outside the web root.
- Validate archive expansion limits to mitigate zip bombs.
- Do not render untrusted HTML from workbook cells.
- Escape formula-like values when exporting CSV previews.

---

## 19. Observability

Every run must record:

- stage start/end
- tool invocation
- duration
- input/output asset references
- deterministic or model-based method
- model ID
- token/latency metrics when available
- warning/error
- retry count
- confidence contribution

Create a technical-log endpoint but keep it hidden behind `View Technical Log` in the UI.

Use correlation IDs:

- `request_id`
- `workbook_id`
- `run_id`
- `stage_id`
- `tool_call_id`

---

## 20. Error handling

Use typed error codes:

- `UNSUPPORTED_FILE_TYPE`
- `FILE_TOO_LARGE`
- `ENCRYPTED_WORKBOOK`
- `CORRUPT_WORKBOOK`
- `UNSAFE_ARCHIVE`
- `PARSER_FAILURE`
- `UNSUPPORTED_WORKBOOK_FEATURE`
- `LM_STUDIO_UNAVAILABLE`
- `MODEL_NOT_CONFIGURED`
- `MODEL_STRUCTURED_OUTPUT_FAILURE`
- `VISION_PROCESSING_FAILURE`
- `JOB_QUEUE_UNAVAILABLE`
- `PROCESSING_CANCELLED`
- `PACKAGE_WRITE_FAILURE`

Show business-friendly messages and preserve technical details for logs.

The pipeline should support partial completion. For example, deterministic extraction can complete even if semantic interpretation fails.

---

## 21. Testing strategy

### 21.1 Test workbook fixtures

Create synthetic workbooks under `backend/tests/fixtures/workbooks/`:

1. `01_clean_table.xlsx`
   - one clean table

2. `02_multiple_sheets.xlsx`
   - customer, orders, and reference sheets
   - cross-sheet lookup

3. `03_multiple_tables_one_sheet.xlsx`
   - unrelated tables and notes

4. `04_multirow_headers.xlsx`
   - merged and hierarchical headers

5. `05_repeated_blocks.xlsx`
   - one block per region

6. `06_form_layout.xlsx`
   - label-value fields

7. `07_formula_model.xlsx`
   - inputs, calculations, outputs
   - cross-sheet formulas

8. `08_hidden_sheets.xlsx`
   - hidden reference and calculation sheets

9. `09_images.xlsx`
   - logo, screenshot, scanned table, and record-linked photograph

10. `10_charts.xlsx`
    - charts with source ranges

11. `11_external_links.xlsx`
    - inaccessible external workbook reference

12. `12_macro_enabled.xlsm`
    - macro present but never executed

13. `13_formula_errors.xlsx`
    - `#REF!`, inconsistent formulas, hard-coded override

14. `14_complex_combined.xlsx`
    - multi-sheet, formulas, images, charts, notes, and repeated blocks

### 21.2 Golden outputs

For important fixtures, store expected:

- workbook manifest
- sheet/region structure
- normalized table schema
- formula edges
- image locations
- review issues
- package manifest

Golden tests must ignore non-deterministic IDs and timestamps.

### 21.3 Unit tests

Cover:

- file validation
- hashing
- workbook manifest creation
- sheet visibility
- merged-header normalization
- region detection rules
- formula tokenization
- cross-sheet reference extraction
- visual-anchor extraction
- content-unit generation
- provenance generation
- directive parsing validation
- impact analysis
- confidence aggregation

### 21.4 Integration tests

Cover:

- upload to completed deterministic package
- queued run lifecycle
- SSE progress
- model unavailable fallback
- feedback to child run
- asset reuse during incremental reprocessing
- package download
- run comparison

### 21.5 Frontend tests

Cover:

- upload validation
- file drop
- workbook filters
- run filters
- progress reconnection
- review action flow
- reprocess drawer
- run comparison
- empty and error states

### 21.6 End-to-end acceptance flow

1. Upload `14_complex_combined.xlsx`.
2. Select knowledge extraction.
3. Start analysis.
4. Observe stage progress.
5. Open output.
6. Preview a normalized table.
7. Preview a visual asset.
8. Resolve one review item.
9. Enter feedback changing a header row and field mapping.
10. Start impacted-assets reprocessing.
11. Compare runs.
12. Accept the latest run.
13. Download the package.

---

## 22. Acceptance criteria

The MVP is complete when:

1. The three main screens visually match the supplied screenshots closely.
2. A user can upload a supported workbook from Home.
3. The workbook appears once in My Workbooks.
4. Every processing attempt appears in Run History.
5. Processing runs asynchronously and exposes recoverable progress.
6. The system generates a manifest, normalized tables, semantic units, embedding chunks, graph nodes/edges, media assets, and a quality report.
7. Images are extracted, located, classified, and linked to nearby workbook context.
8. Formulas generate dependency edges and human-readable business-rule candidates.
9. Every generated asset has provenance.
10. Low-confidence findings create review items.
11. Natural-language feedback is converted into structured directives.
12. A feedback rerun creates a child run and reuses unaffected approved assets.
13. The user can compare runs and accept the preferred version.
14. The complete package can be downloaded as a ZIP.
15. The application works when LM Studio is online.
16. Deterministic extraction still works with a clear degraded status when LM Studio is offline.
17. Macros are never executed.
18. Automated tests cover the core flow.

---

## 23. Implementation sequence for Codex

Implement in this order. Do not jump directly into agent prompts before the domain model and deterministic processing are stable.

### Phase 1: Scaffold

- Create monorepo.
- Configure frontend, backend, database, Redis, linting, formatting, tests, and Docker Compose.
- Add `.env.example`.
- Add health endpoints.

### Phase 2: UI shell and screenshot-faithful screens

- Build shared shell.
- Build Home.
- Build My Workbooks.
- Build Run History.
- Use mocked typed API data temporarily.
- Add responsive behavior.

### Phase 3: Persistence and upload flow

- Implement database models and migrations.
- Implement local object storage.
- Implement workbook upload.
- Implement workbook list and run list.
- Connect UI to real APIs.

### Phase 4: Job queue and run lifecycle

- Implement RQ worker.
- Implement stage state machine.
- Implement SSE events.
- Build processing screen.

### Phase 5: Deterministic workbook processing

- File safety and manifest.
- Sheets, tables, formulas, named ranges, images, charts, comments, and links.
- Region and table normalization.
- Canonical package writer.
- Golden tests.

### Phase 6: LM Studio and agent runtime

- Model registry.
- Reasoning, vision, and embedding adapters.
- Deep Agents runtime adapter.
- Supervisor and typed tools.
- Structured semantic outputs.
- Degraded-mode behavior.

### Phase 7: Review and feedback

- Review item APIs and UI.
- Feedback drawer.
- Feedback interpreter.
- Processing directives.
- Impact analysis.
- Incremental child runs.

### Phase 8: Outputs and comparison

- Workbook detail.
- Asset previews.
- Package download.
- Run comparison.
- Accept current version.

### Phase 9: Hardening

- Security checks.
- Error states.
- Performance profiling.
- E2E tests.
- Documentation.

---

## 24. Codex working rules

1. Read this file and all screenshots before coding.
2. Create a short implementation checklist in the repository and update it as work progresses.
3. Prefer small, testable modules.
4. Keep UI components under roughly 250 lines when practical.
5. Keep API route handlers thin.
6. Put business logic in services and processing modules.
7. Use typed schemas end to end.
8. Never store large workbook content directly in relational database columns.
9. Never execute workbook macros.
10. Never rely on the LLM for facts a deterministic parser can provide.
11. Validate every model output.
12. Preserve provenance throughout transformations.
13. Do not add features outside this specification until the core flow is complete.
14. Do not over-design the UI.
15. Run formatting, linting, unit tests, integration tests, and frontend tests before marking a phase complete.
16. When a library cannot expose a workbook feature, document the limitation and emit a review/quality item instead of silently dropping it.
17. Keep the application usable without cloud accounts.
18. Create clear README instructions for starting LM Studio, Redis, backend, worker, and frontend.

---

## 25. Developer commands

Provide a `Makefile` with at least:

```text
make install
make dev
make backend
make worker
make frontend
make redis
make test
make test-backend
make test-frontend
make lint
make format
make create-fixtures
make seed-demo
make verify-lmstudio
```

Recommended local startup:

```text
Terminal 1: LM Studio local server
Terminal 2: make redis
Terminal 3: make backend
Terminal 4: make worker
Terminal 5: make frontend
```

Docker Compose may run the database, Redis, backend, worker, and frontend, but LM Studio is expected to run on the host machine.

---

## 26. README requirements

The generated repository README must include:

- Product overview
- Architecture diagram
- Prerequisites
- LM Studio setup
- Model role configuration
- Local startup
- Docker startup
- How to upload a workbook
- Output package explanation
- How feedback and reprocessing work
- Test commands
- Known limitations
- Security note about macros

---

## 27. Final product behavior summary

The completed application should feel like this:

```text
Upload workbook
    ↓
System profiles workbook and selects a processing path
    ↓
Deterministic tools extract structure, data, formulas, visuals, and lineage
    ↓
Local agents interpret semantics and ambiguity
    ↓
System validates and creates a normalized Workbook Knowledge Package
    ↓
User reviews only uncertain items
    ↓
User gives feedback
    ↓
Feedback becomes processing directives
    ↓
Only impacted assets are reprocessed
    ↓
User compares and accepts the improved run
```

The user should experience a simple workbook-processing product. The implementation should provide a rigorous, traceable, multimodal knowledge-extraction platform underneath it.
