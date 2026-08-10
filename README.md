# Knowledge Graph Builder

Local-first proof-of-concept for generating graph-ready knowledge assets from structured and unstructured sources.

This repository contains **Milestones 0–10**:

- screenshot-matched application shell and Build workflow
- SQLite-backed projects and source metadata
- validated local filesystem uploads
- canonical Pydantic knowledge asset models
- typed SQL/JSON/CSV/PDF/DOCX/image parsing and OCR fallback
- configurable LM Studio model provider with structured-output retry
- independently callable knowledge extraction, semantic mapping, entity-resolution, graph-schema, and quality tools
- Deep Agents supervisor planning with Source Analyst, Knowledge Engineer, Graph Modeller, and Quality Reviewer specialists
- durable LangGraph run orchestration, observable events, and a validation-driven re-plan path
- browsable graph asset packages with filters, pagination, evidence inspection, quality metrics, and persistent review decisions
- Neo4j Aura health, approved-only idempotent publication, publication history, and safe package-to-graph mapping
- an interactive Cytoscape graph explorer with search, node/relationship filters, traversal depth, counts, legend, node details, relationship navigation, provenance evidence, and guarded read-only Cypher
- production-style loading, empty, failure, and responsive states; a validated synthetic demo pack; automated checks; setup/runbook documentation; and a guarded demo reset command

The planned POC milestones are complete.

## Prerequisites

- Node.js 20+
- Python 3.12+
- `uv`

## Configure

```bash
cp .env.example .env
```

External integrations do not need to be configured for deterministic parsing and the local shell. The header reports live LM Studio and Neo4j Aura connectivity. Publishing remains disabled until valid Aura credentials are configured.

For LM Studio extraction, set the orchestrator and knowledge model environment variables to model identifiers loaded in LM Studio. Image OCR also requires the local `tesseract` executable; document and schema parsing work without it.

For complete onboarding instructions, see [Local setup](docs/SETUP.md). To exercise the synthetic procurement workflow from upload through graph exploration, follow the [end-to-end demo runbook](docs/DEMO_RUNBOOK.md).

## Run the backend

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload --port 8000
```

The health endpoint is available at `http://localhost:8000/api/v1/health` (with `/health` retained as a convenience alias).

## Run the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite development server proxies `/api` requests to the backend.

## Verify

```bash
cd backend && uv run python -m pytest
cd frontend && npm test -- --run && npm run build
```

Or run the complete verification suite from the repository root:

```bash
make test
```

## Reset demo state

```bash
make reset-demo
```

The reset command previews exact local targets and requires confirmation. Neo4j cleanup is never implicit; see the demo runbook for the explicitly project-scoped option.

## Routes

- `/` — Build
- `/assets` — Graph Assets
- `/graph` — Graph Explorer

## Implemented API

- `GET /api/v1/health`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `PATCH /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/sources`
- `GET /api/v1/projects/{project_id}/sources`
- `DELETE /api/v1/projects/{project_id}/sources/{source_id}`
- `POST /api/v1/projects/{project_id}/runs`
- `GET /api/v1/projects/{project_id}/runs/{run_id}`
- `GET /api/v1/projects/{project_id}/runs/{run_id}/events`
- `GET /api/v1/projects/{project_id}/runs/{run_id}/stream`
- `GET /api/v1/projects/{project_id}/assets`
- `GET /api/v1/projects/{project_id}/assets/{entities|relationships|concepts|facts|events}`
- `POST /api/v1/projects/{project_id}/assets/{asset_id}/{approve|review|reject}`
- `POST /api/v1/projects/{project_id}/publish/neo4j`
- `GET /api/v1/projects/{project_id}/publish/status`
- `GET /api/v1/projects/{project_id}/graph`
- `GET /api/v1/projects/{project_id}/graph/node/{node_id}`
- `POST /api/v1/projects/{project_id}/graph/query`

Knowledge extraction tools are orchestrated through a durable LangGraph run. The Build screen surfaces run events, the Graph Assets screen provides review, and only approved assets are published through parameterized Neo4j `MERGE` operations. The Graph Explorer reads that project-scoped graph through Cytoscape and exposes only guarded, read-only Cypher queries.
