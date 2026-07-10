# Deployment

## Prerequisites

- Python 3.11 runtime for the Databricks App.
- Databricks CLI authenticated to the target workspace.
- A Unity Catalog catalog with Bronze, Silver, and operations schemas.
- Governed Volumes containing immutable source files.
- A Databricks App service principal or workload identity.
- Parser Workflow jobs or another approved Databricks-native parser invocation.
- MLflow experiment permissions.
- Azure managed identity access to Document Intelligence when that adapter is enabled.

The repository does not contain workspace URLs, tokens, organization IDs, real catalog names, job IDs, Azure keys, or source credentials.

## Local installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
cp .env.example .env
make check
make run
```

Local mode requires:

```dotenv
APP_ENV=local
USE_MOCK_TOOLS=true
DRY_RUN_DEFAULT=true
```

The application listens on port 8000 when started through `make run`.

## Configuration reference

| Variable | Required in production | Description |
|---|---:|---|
| `APP_ENV` | yes | Environment label included in audit and trace metadata |
| `USE_MOCK_TOOLS` | yes | Must be `false` after a production repository is bound |
| `DRY_RUN_DEFAULT` | recommended | Default action safety behavior |
| `LOG_LEVEL` | no | Structured log level; default `INFO` |
| `DATABRICKS_HOST` | runtime supplied | Workspace host, normally injected by Databricks auth |
| `DATABRICKS_CATALOG` | yes | Governed catalog |
| `DATABRICKS_BRONZE_SCHEMA` | yes | Bronze metadata schema |
| `DATABRICKS_SILVER_SCHEMA` | yes | Silver output schema |
| `DATABRICKS_OPERATIONS_SCHEMA` | yes | Assessments, recovery, review, benchmark, and audit schema |
| `DATABRICKS_WORKFLOW_JOB_IDS` | for Workflow parsing | JSON map such as `{"databricks_primary":123}` |
| `DATABRICKS_MODEL_ENDPOINT` | optional | Approved serving/function endpoint |
| `MLFLOW_EXPERIMENT` | yes | Experiment path for agent traces |
| `QUALITY_POLICY_FILE` | yes | Quality policy YAML path |
| `ROUTING_POLICY_FILE` | yes | Routing policy YAML path |
| `ALLOWED_SOURCE_PREFIXES` | yes | JSON list of allowed ADLS/Volume prefixes |
| `SOURCE_SAMPLE_MAX_BYTES` | no | Bounded sample size; default 65536, maximum 1 MiB |
| `MAXIMUM_AUTOMATIC_RETRIES_PER_PARSER` | no | Default 1 |
| `MAXIMUM_TOTAL_PARSER_ATTEMPTS` | no | Default 3 |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | when enabled | Azure service endpoint, not a secret |
| `AZURE_DOCUMENT_INTELLIGENCE_AUTH_MODE` | no | Prefer `managed_identity` |
| `AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID` | no | Default `prebuilt-layout` |
| `AZURE_DOCUMENT_INTELLIGENCE_TIMEOUT_SECONDS` | no | Provider timeout |
| `AZURE_DOCUMENT_INTELLIGENCE_ALLOW_API_KEY` | no | Explicitly enables fallback key auth |
| `AZURE_DOCUMENT_INTELLIGENCE_API_KEY` | only for fallback | Inject from a secret; never place in `.env.example` |
| `CUSTOM_PARSER_ENABLED` | no | Enables the custom adapter |
| `CUSTOM_PARSER_URL` | when enabled | Approved service endpoint |

Nested `TABLE_MAPPINGS` may be supplied as Pydantic-compatible JSON to map logical contracts to workspace table names. Keep every mapped object within an allowed catalog/schema.

## Unity Catalog objects

The setup notebook creates example operational tables. A production deployment should provision at minimum:

- Bronze file manifest and parser run tables;
- Silver document and element output tables;
- quality assessment table;
- recovery attempt table;
- parser benchmark table;
- human review queue;
- immutable audit event store;
- approved source Volumes.

Run `notebooks/01_setup_tables.py` only after reviewing names and ownership. Review `resources/uc_functions.sql`, substitute bundle variables through deployment configuration, and register functions under a controlled owner using `notebooks/02_register_uc_functions.py`.

## Permissions

The app identity normally needs:

- `USE CATALOG` on the selected catalog;
- `USE SCHEMA` on Bronze, Silver, and operations schemas;
- `SELECT` on approved Bronze/Silver metadata and outputs;
- `READ VOLUME` on specific source Volumes;
- `EXECUTE` on approved UC functions;
- permission to run only configured parser jobs;
- permission to write only operational tables/functions required by approved actions;
- MLflow experiment read/write permission.

Do not grant unrestricted SQL, catalog ownership, broad Volume access, secret read-all, or permission to edit parser Workflows.

## Databricks Asset Bundle

Validate each target before deployment:

```bash
databricks bundle validate -t dev
databricks bundle validate -t test
databricks bundle validate -t prod
```

Deploy:

```bash
databricks bundle deploy -t dev
```

The sample `databricks.yml` provides dev, test, and prod targets plus app resource placeholders. Before production, add the workspace root path, `run_as` service principal, explicit permissions, job IDs, catalog/schema values, and environment-specific policy bindings. Use the Databricks CLI version approved by the organization; if app source deployment is separate in that version, deploy the app using the workspace-supported Apps command after the bundle resources exist.

## Azure Document Intelligence

1. Provision or identify the Azure Document Intelligence resource.
2. Configure private connectivity and DNS where required.
3. Grant the Databricks App identity permission through managed identity.
4. Set only the endpoint and model ID in app configuration.
5. Enable API-key fallback only if managed identity is unavailable and policy permits it.
6. Store fallback keys in Databricks secrets or an App resource binding.
7. Exercise the contract normalization test against synthetic content before production documents.

## Workflow binding

Create one governed job ID per parser or route multiple parsers through a single processing job with an allowlisted parser parameter. The job must accept document ID, source URI, parser ID/config, source run, recovery ID, and idempotency key. It must create a new run/version and must not overwrite previous Silver output.

## MLflow tracing

Set `MLFLOW_EXPERIMENT` to an experiment writable by the app identity. Operation spans include identifiers, actor, environment, and operation mode. Do not add raw credentials or unrestricted document content as attributes. Configure retention, access controls, and sampling according to data classification.

## Readiness verification

```bash
curl -s https://APP_HOST/health
curl -s https://APP_HOST/ready
```

Then perform, in order:

1. mock or synthetic investigation;
2. parser comparison using historical metrics;
3. dry-run recovery without approval;
4. live recovery with a test approval reference;
5. verification of a new run ID and recovery-attempt audit row;
6. denial test using missing/invalid approval;
7. source allowlist and path traversal tests.

## Production integration blocker

`build_orchestrator` intentionally raises when `USE_MOCK_TOOLS=false` because a generic production repository cannot safely assume workspace SQL/functions. Implement and inject the governed repository before deploying with production settings. This fail-closed behavior prevents synthetic data from being served accidentally.

## Rollback

Retain the previous bundle deployment and policy version. Roll back application code using the organization’s bundle release process, then restore the previous routing-policy version. Do not delete parser runs, assessments, or recovery records during rollback. If a parser job is unsafe, remove its routing eligibility and run permission rather than altering historical data.
