# Local setup

This guide takes a new developer from a fresh clone to a running Knowledge Graph Builder POC.

## 1. Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- `uv`
- LM Studio with its OpenAI-compatible local server enabled
- a Neo4j Aura database
- optional: Tesseract for OCR of PNG/JPEG sources

## 2. Install

From the repository root:

```bash
make install
cp .env.example .env
```

## 3. Configure LM Studio

Load an instruction-following model in LM Studio and start the local server on port `1234`. Set both model variables to exact model identifiers returned by LM Studio:

```dotenv
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_ORCHESTRATOR_MODEL=your-loaded-model-id
LMSTUDIO_KNOWLEDGE_MODEL=your-loaded-model-id
LMSTUDIO_TIMEOUT_SECONDS=120
```

`LMSTUDIO_EMBEDDING_MODEL` is optional for this POC. The application uses deterministic fallbacks if planning is unavailable, but model-backed extraction requires the knowledge model.

## 4. Configure Neo4j Aura

Copy the connection values from the Aura console:

```dotenv
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

Never commit `.env`; it is ignored by Git.

## 5. Start the application

In separate terminals, from the repository root:

```bash
make api
```

```bash
make web
```

Open `http://localhost:5173`. Both header connection indicators should report `Connected`. API documentation is available at `http://localhost:8000/docs`.

## 6. Verify the installation

```bash
make test
```

This runs backend tests, frontend linting, the production build, and frontend tests.

## Troubleshooting

- **LM Studio unavailable:** confirm its local server is running, the port matches `LMSTUDIO_BASE_URL`, and the configured model identifiers are loaded.
- **LM Studio request timed out:** increase `LMSTUDIO_TIMEOUT_SECONDS` for a slower or larger local model, then restart the API.
- **Neo4j disconnected:** use the `neo4j+s://` Aura URI and confirm the username, password, and database name.
- **Image text is empty:** install Tesseract and confirm `tesseract --version` works in the same shell that starts the API.
- **Stale project after a reset:** reload the Build page. Missing project and run identifiers are cleared automatically.
- **Port already used:** stop the process using port `8000` or `5173` before starting the corresponding service.

Continue with the [demo runbook](DEMO_RUNBOOK.md).
