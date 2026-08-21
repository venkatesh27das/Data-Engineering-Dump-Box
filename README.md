# Workbook Agent

Workbook Agent is a local-first application that turns Excel workbooks into structured, traceable knowledge packages. It preserves workbook structure, formulas, tables, charts, images, relationships, and provenance instead of flattening everything into plain text.

## Highlights

- Upload and analyze `.xlsx`, `.xlsm`, and `.xlsb` workbooks.
- Extract sheets, regions, tables, formulas, charts, images, named ranges, validations, connections, and other Excel metadata.
- Inspect every generated artifact in the run-specific **Asset Explorer**.
- Follow extraction stages, agent activity, dependencies, and failures in **Processing Trace**.
- Reprocess a run with feedback and compare or accept generated versions.
- Continue using the deterministic pipeline when LM Studio is unavailable.
- Keep workbook data, model calls, packages, and vectors on the local machine by default.

## Architecture

```text
React UI ── REST/SSE ── FastAPI ── SQLite + local object storage
                              ├── background workbook pipeline
                              ├── specialist agents + structured fallback
                              └── LM Studio chat, vision, and embeddings
```

The local pipeline handles workbook profiling, planning, extraction, indexing, validation, packaging, and review. If LM Studio is available, the application can add local reasoning, vision interpretation, entity extraction, and embeddings. Model failures degrade gracefully and do not prevent deterministic package creation.

## Quick start

### Prerequisites

- macOS or Linux
- [Node.js](https://nodejs.org/) 20 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Optional: [LM Studio](https://lmstudio.ai/) for local AI capabilities
- Optional: Docker Desktop for container-based startup

### Install

```bash
git clone https://github.com/venkatesh27das/Data-Engineering-Dump-Box.git
cd Data-Engineering-Dump-Box
./install.sh
```

The installer creates `.env` from `.env.example` when needed, installs the locked backend and frontend dependencies, and keeps an existing `.env` unchanged.

Useful installer options:

```bash
./install.sh --with-fixtures  # also generate backend test workbooks
./install.sh --check          # install, lint, test, and build
./install.sh --help
```

### Run

Start the API:

```bash
make backend
```

In a second terminal, start the web application:

```bash
make frontend
```

Then open:

- Application: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/v1/health>

The development server includes an in-process background worker, so Redis is not required for the standard local workflow.

## Using the application

1. Upload an Excel workbook from **Home**.
2. Select the processing purpose and choose **Analyze Workbook**.
3. Follow live progress on the run overview.
4. Open **Assets** to browse generated sheets, tables, formulas, charts, images, semantic units, and package files.
5. Open **Processing Trace** to inspect stage durations, agent activity, lineage, dependencies, and errors.
6. Download the completed knowledge package, or reprocess it with feedback.

For failed runs, the trace shows the recorded error and the last successful stage. Use **Retry** after addressing the failure; incomplete runs do not expose a misleading package download.

## Sample workbooks

The [`test_files`](./test_files) directory contains three upload-ready examples:

- `16_simple_inventory.xlsx` — basic inventory data and formulas.
- `17_intermediate_sales_model.xlsx` — multiple sheets, lookups, summaries, and charts.
- `18_advanced_operations_pack.xlsx` — complex formatting, validations, relationships, formulas, and operational reporting.

Generated backend fixtures can also be recreated with:

```bash
make create-fixtures
```

## Knowledge package

Completed packages are stored under:

```text
data/storage/workbooks/{workbook_id}/runs/{run_id}/package/
```

A package can include:

- workbook and processing manifests
- sheet, region, table, formula, chart, and image metadata
- normalized Parquet tables
- contextual semantic units and embedding-ready chunks
- local embedding vectors
- graph nodes, edges, and lineage records
- validation results and review items

Runtime database/storage files, `backend/data/`, and `outputs/` are intentionally excluded from Git.

## LM Studio setup

1. Load suitable chat, vision, and embedding models in LM Studio.
2. Start the OpenAI-compatible local server on port `1234`.
3. Keep the role variables blank for automatic model selection, or set them explicitly in `.env`.
4. Run `make verify-lmstudio`, or open **Settings → Test capabilities**.

Common configuration:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | Local OpenAI-compatible endpoint |
| `LLM_REASONING_MODEL` | empty | Explicit reasoning model override |
| `LLM_VISION_MODEL` | empty | Explicit vision model override |
| `EMBEDDING_MODEL` | empty | Explicit embedding model override |
| `AUTO_SELECT_MODELS` | `true` | Discover suitable loaded models |
| `ENABLE_VISION` | `true` | Enable image and chart interpretation |
| `ENABLE_OCR` | `true` | Enable image text extraction |
| `ENABLE_EMBEDDINGS` | `true` | Generate vector embeddings when available |
| `STORAGE_ROOT` | `./data/storage` | Local package and upload storage |
| `MAX_UPLOAD_MB` | `200` | Maximum workbook upload size |

When the API runs in Docker on macOS or Windows, set `LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1`.

## Development commands

```bash
make install          # run the installer
make backend          # FastAPI development server
make frontend         # Vite development server
make test             # backend and frontend tests
make lint             # Python and TypeScript linting
make check            # lint, test, and production frontend build
make format           # format supported source files
make create-fixtures  # recreate generated backend fixtures
make seed-demo        # seed demo records
make verify-lmstudio  # probe local model capabilities
```

## Docker

```bash
docker compose up --build
```

The Compose stack starts the API, web application, and Redis boundary. The API still uses its built-in worker, and local development does not require Redis.

## Repository layout

```text
backend/       FastAPI API, processing pipeline, services, and tests
frontend/      React/Vite application and component tests
test_files/    upload-ready example Excel workbooks
data/          ignored local database, uploads, and packages
install.sh     reproducible local dependency installer
Makefile       common development commands
```

## Troubleshooting

- **LM Studio is offline:** deterministic extraction still works; the run records model-backed capabilities as unavailable or degraded.
- **A workbook fails to parse:** open **Processing Trace** for the exact error, verify the file opens in Excel or LibreOffice, then retry the run.
- **Port 8000 or 5173 is busy:** stop the existing process or run the respective server on a different port.
- **Dependencies look stale:** rerun `./install.sh`; it uses `uv.lock` and `package-lock.json` for reproducible installs.
- **You need a clean local dataset:** stop the app and remove only the intended local runtime database/storage files. Do not commit generated package content.

## Known limitations

- The default development worker runs in-process; the Redis/RQ boundary is prepared for distributed execution.
- Formula expressions are inspected but not recalculated.
- `.xlsb` support covers values, regions, tables, and semantic units; some formula, drawing, and visibility details depend on what the binary parser exposes.
- Uploaded macros and embedded code are detected and statically recorded but never executed.
- Encrypted workbooks are rejected; password recovery is not attempted.
- Local model speed and quality depend on the loaded models and available hardware.

## Security and privacy

Workbook content remains local by default. Filenames are sanitized, upload size and archive expansion are bounded, HTML from cells is not rendered, and cell values are not written to application logs. VBA and embedded code are never executed.
