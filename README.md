# Workbook Agent

Workbook Agent is a local-first application that turns Excel workbooks into traceable knowledge packages. It preserves sheets, regions, tables, formulas, images, charts, relationships, and source provenance instead of flattening the workbook into loose text.

## Architecture

```text
React UI ── REST/SSE ── FastAPI ── SQLite + local object storage
                              ├── background workbook pipeline
                              ├── Deep Agents runtime + structured fallback
                              └── LM Studio chat, vision, and embeddings
```

The deterministic pipeline remains usable when LM Studio is offline. When it is online, specialist planning, semantic, visual, validation, and feedback agents use local models, and embedding vectors are written into the package. Agent failures are isolated and marked as degraded rather than blocking deterministic package creation. Uploaded macros are detected and recorded but are never executed.

## Prerequisites

- Node.js 20+
- Python 3.11+ (managed automatically by `uv`)
- `uv`
- Optional: Docker Desktop and LM Studio

## Local startup

```bash
cp .env.example .env
make install
make create-fixtures
make backend
```

In a second terminal:

```bash
make frontend
```

Open <http://localhost:5173>. The API documentation is at <http://localhost:8000/docs>.

The API uses a lightweight in-process background worker by default so the core flow works without Redis. `make redis` and `make worker` are provided for the production queue migration boundary.

## LM Studio setup

1. Load suitable reasoning, vision, and embedding models in LM Studio.
2. Start its OpenAI-compatible local server on port `1234`.
3. Leave model role variables blank for automatic local selection, or set `LLM_REASONING_MODEL`, `LLM_VISION_MODEL`, and `EMBEDDING_MODEL` explicitly.
4. Run `make verify-lmstudio`, or use **Settings → Test capabilities** for structured chat, image understanding, and vector probes.

The current automatic preferences select a Qwen chat model for reasoning, a vision-capable Gemma/VL model for images, and a model containing `embed` for vectors. Settings changed through `PUT /api/v1/models/config` are saved locally in `data/model_config.json`.

When the API runs in Docker on macOS or Windows, use `http://host.docker.internal:1234/v1`.

## Docker startup

```bash
docker compose up --build
```

## Using the application

Drop an `.xlsx`, `.xlsm`, or `.xlsb` file on Home, choose a purpose, and select **Analyze Workbook**. The run page streams recoverable progress. Completed output is organized under `data/storage/workbooks/{id}/runs/{id}/package` and can be downloaded as a ZIP.

The package includes a workbook manifest, sheet/table/formula/image/chart metadata, normalized Parquet tables, contextual semantic units, embedding-ready chunks, generated vectors, graph nodes/edges, lineage, quality results, and review items. Agent execution mode and chosen models are recorded in the manifest.

Advanced Excel coverage includes multi-row merged headers, repeated data blocks, label/value forms, external links, workbook connections, query-table and Power Query package detection, pivot metadata, conditional formatting, data validation, static VBA inspection, chart series/axis/source interpretation, embedded-image OCR, and value/table/semantic extraction for `.xlsb` files.

Reprocessing accepts plain-language feedback, converts it to typed directives, creates a child run, and limits work to impacted assets where possible. Runs can be compared and accepted as the workbook's current version.

## Tests and quality

```bash
make test
make lint
make format
```

Synthetic workbook fixtures can be recreated with `make create-fixtures` and demo rows with `make seed-demo`.

## Known limitations

- The first implementation uses an in-process worker; the Redis/RQ adapter boundary is scaffolded for distributed operation.
- Local inference speed depends on the selected models and hardware. A model-backed run can take longer than deterministic extraction.
- OCR uses the configured local vision model and stores verbatim text blocks with image provenance. If vision is unavailable, the image remains packaged for later interpretation.
- Impacted-assets feedback is converted to typed directives; the current local worker safely rebuilds the canonical package so cross-file consistency is preserved.
- Excel formulas are inspected, not recalculated.
- `.xlsb` value, region, table, and semantic-unit extraction is supported. Formula expressions, hidden-sheet state, and drawings remain explicitly flagged when the binary parser cannot expose them.
- Encrypted workbooks are rejected; password recovery is never attempted.

## Security and privacy

Workbook content stays on the local machine by default. Filenames are sanitized, upload size and archive expansion are bounded, HTML is not rendered from cells, and cell values are not logged. VBA and embedded code are only detected and statically recorded—never executed.
