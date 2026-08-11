# Local setup

This guide takes a new developer from a fresh clone to a running Knowledge Graph Builder POC.

## 1. Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer
- [`uv`](https://docs.astral.sh/uv/)
- LM Studio **or** an OpenAI-compatible AI gateway
- optional: a Neo4j Aura/Neo4j database
- optional: Tesseract for OCR of PNG/JPEG sources

## 2. Install and create configuration

From the repository root:

```bash
./scripts/run-local.sh --install
```

This installs both dependency sets, creates `.env` from `.env.example` when needed, validates the configuration, and starts the API and web application. If model credentials are not ready yet, create and edit the file first:

```bash
cp .env.example .env
```

Never commit `.env`; it is ignored by Git.

## 3. Configure one model provider

### LM Studio

Load an instruction-following model in LM Studio and start its OpenAI-compatible server, normally on port `1234`. Use exact model identifiers from `GET http://localhost:1234/v1/models`:

```dotenv
AI_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_ORCHESTRATOR_MODEL=your-loaded-model-id
LMSTUDIO_KNOWLEDGE_MODEL=your-loaded-model-id
LMSTUDIO_TIMEOUT_SECONDS=120
LMSTUDIO_CONNECT_TIMEOUT_SECONDS=10
```

### OpenAI-compatible AI gateway

Use a gateway, proxy, or hosted endpoint that exposes the OpenAI API shape:

```dotenv
AI_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=https://gateway.example.com/v1
OPENAI_COMPATIBLE_API_KEY=replace-with-your-secret
OPENAI_COMPATIBLE_ORCHESTRATOR_MODEL=provider/model-name
OPENAI_COMPATIBLE_KNOWLEDGE_MODEL=provider/model-name
OPENAI_COMPATIBLE_TIMEOUT_SECONDS=120
OPENAI_COMPATIBLE_CONNECT_TIMEOUT_SECONDS=10
```

The key is sent as a Bearer token. The selected gateway must support `/models`, `/chat/completions`, and JSON Schema structured output. The embedding model and `/embeddings` endpoint are optional for the current workflow.

For either provider, the orchestrator and knowledge roles may use the same model. A smaller orchestrator can reduce planning latency, while the knowledge role benefits from reliable structured output and enough context for the uploaded sources.

## 4. Configure Neo4j (optional)

Copy the connection values from Neo4j Aura or your Neo4j deployment:

```dotenv
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=replace-with-your-password
NEO4J_DATABASE=neo4j
```

Without Neo4j, source processing, run monitoring, and Graph Assets review still work. Publication and Graph Explorer require a connection.

## 5. Start the application

The recommended command starts both services and stops both when you press `Ctrl+C`:

```bash
./scripts/run-local.sh
```

Useful launcher options:

```bash
./scripts/run-local.sh --install  # synchronize dependencies, then start
./scripts/run-local.sh --check    # validate setup without starting
./scripts/run-local.sh --help
```

Open `http://127.0.0.1:5173`. API documentation is at `http://127.0.0.1:8000/docs`.

For independent development servers, use separate terminals:

```bash
make api
```

```bash
make web
```

## 6. Verify the installation

```bash
make test
```

This runs backend tests, frontend linting, the production build, and frontend tests.

## Troubleshooting

- **Provider shows Disconnected:** confirm `AI_PROVIDER` selects the intended provider, the base URL includes `/v1`, and `GET <base-url>/models` accepts the configured Bearer key when using a gateway.
- **LM Studio unavailable:** confirm its local server is running, the port matches `LMSTUDIO_BASE_URL`, and the configured model identifiers are loaded.
- **Request timed out:** increase the selected provider's `*_TIMEOUT_SECONDS`, reduce the run token budget, or use a faster model. Chat completion read timeouts are retried once; connection failures still use the shorter `*_CONNECT_TIMEOUT_SECONDS` value.
- **Structured output fails:** choose a model/gateway that supports OpenAI JSON Schema response format. The application makes one corrective retry when returned JSON does not validate.
- **Neo4j disconnected:** use the `neo4j+s://` Aura URI and confirm the username, password, and database name.
- **Image text is empty:** install Tesseract and confirm `tesseract --version` works in the shell that starts the API.
- **Stale project after a reset:** reload the Build page. Missing project and run identifiers are cleared automatically.
- **Port already used:** stop the process using port `8000` or `5173`. The launcher reports the owner and does not terminate it.

Continue with the [demo runbook](DEMO_RUNBOOK.md).
