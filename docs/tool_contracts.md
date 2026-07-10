# Tool contracts

## Design rules

Tools form the security boundary between the orchestrator and infrastructure. The agent may select only registered tools with Pydantic-validated inputs. It never receives a generic SQL executor, shell tool, arbitrary filesystem reader, or credential-bearing client.

Tool descriptions must begin with `READ ONLY` or `STATE CHANGING`. A state-changing tool must receive a `WriteContext` containing:

- non-empty actor identity;
- valid `ApprovalContext` with `approved=true`, approval reference, and approver identity;
- reason;
- correlation ID;
- dry-run flag;
- operation-specific idempotency key.

Missing write context raises `ApprovalRequiredError`. Dry-run returns a plan/result without performing the mutation.

## Read inventory

| Tool | Required selector | Output | Purpose |
|---|---|---|---|
| `get_document_context` | `document_id`, optional `run_id` | `DocumentContext` | Load Bronze identity, parser run, Silver document, elements, and document class |
| `get_bronze_manifest` | `document_id` | `BronzeManifest` | Read immutable-source identity and ingestion lineage |
| `get_parser_run` | `run_id` | `ParserRun` | Inspect parser status, configuration, latency, warnings, and error |
| `get_silver_document` | `document_id`, `run_id` | `SilverDocument` | Retrieve normalized document output |
| `get_silver_elements` | `document_id`, `run_id` | list of `SilverElement` | Retrieve page/element-level output and source references |
| `get_quality_assessment` | `document_id`, `run_id` | `QualityAssessment` | Retrieve an existing quality result |
| `get_parser_history` | `document_id` | list of `ParserRun` | Prevent retry loops and support diagnosis |
| `get_batch_failures` | `batch_id`, bounded limit | failure summaries | Investigate a processing batch |
| `get_parser_metrics` | parser IDs and optional class/window | normalized metric rows | Rank parsers and propose policy |
| `read_source_file_sample` | allowlisted URI, byte/page limit | bounded bytes/content | Inspect only the evidence required for diagnosis |

The MVP directly implements `get_document_context`, `get_parser_history`, `get_parser_metrics`, and the bounded Volume reader. The remaining names define the production repository contract and UC/MCP inventory.

## State-changing inventory

| Tool | Idempotency scope | Result |
|---|---|---|
| `create_recovery_attempt` | document + source run + parser/config + strategy | immutable recovery record |
| `trigger_reprocessing_workflow` | recovery operation key | Databricks workflow run ID/status |
| `update_processing_status` | document + target status + correlation | audited status result |
| `submit_human_review` | review ID | `HumanReviewRequest` |
| `quarantine_document` | document + run + reason | quarantine record/status |
| `record_quality_assessment` | assessment ID or document/run/policy version | assessment record |
| `propose_routing_policy` | document class + proposal version | immutable proposal |
| `apply_approved_routing_policy` | proposal + approval reference | applied policy version |

Production functions must reject a repeated key with a conflicting payload. Repeating an identical request returns the original result.

## Parser adapter protocol

All parsers implement:

```python
class ParserAdapter(Protocol):
    parser_id: str

    def is_eligible(self, document: DocumentContext) -> EligibilityResult: ...
    async def parse(self, request: ParserRequest) -> ParserResult: ...
    def estimate_cost(self, request: ParserRequest) -> CostEstimate: ...
    async def health_check(self) -> HealthStatus: ...
```

`ParserResult` normalizes parser identity/version, status, Silver document/elements, latency, cost, warnings, metadata, and structured errors. Raw provider responses must not leak through the API.

### Databricks parser

`DatabricksParserAdapter` is an explicit integration point. Configure one approved invocation mechanism: owned UC SQL function, Workflow task, or model/function endpoint. The adapter does not invent or assume a proprietary parsing API. Without binding, health is unhealthy and parse fails safely with `PARSER_CONFIGURATION_ERROR`.

### Azure Document Intelligence

`AzureDocumentIntelligenceAdapter` uses `DocumentIntelligenceClient.begin_analyze_document`. It prefers `DefaultAzureCredential`; API-key fallback requires both the explicit allow flag and injected secret. It normalizes pages, lines, geometry, tables/cells, source references, latency, and errors. Timeouts become `PARSER_TIMEOUT`, HTTP 429 becomes `PARSER_RATE_LIMIT`, and other provider errors become `PARSER_SERVICE_ERROR`.

### Custom parser

`CustomParserAdapter` supports an approved HTTP URL or Python callable. It is disabled by default. HTTP output must validate as `ParserResult`, and requests use a bounded timeout.

## Workflow client contract

`trigger_parser_run` accepts document ID, source URI, parser ID/config, source run, recovery ID, idempotency key, and dry-run. The SDK implementation maps parser IDs to configured job IDs and passes job parameters as values rather than interpolated SQL. `wait_for_completion` uses bounded exponential polling; terminal status or timeout is returned without infinite loops.

## Source access contract

`VolumeReader` accepts only configured `abfss://` or `/Volumes/` prefixes, rejects `..` traversal, and caps samples at `SOURCE_SAMPLE_MAX_BYTES`. Local files outside governed Volume prefixes and arbitrary workspace paths are rejected. ADLS access must be implemented with a governed storage client rather than a generic URL fetcher.

## SQL and Unity Catalog

SQL templates use named parameters and allowlisted object mappings. `IDENTIFIER(:table_parameter)` is supplied only from trusted configuration, never prompt text. Write operations should be owned UC functions/procedures that independently verify actor, approval, reason, correlation, and idempotency. Examples are in `resources/uc_functions.sql` and `src/processing_quality_agent/sql/`.

## MCP mapping

Managed MCP discovery may expose the same logical tools. The MCP client must validate discovered names against the local registry, validate input/output models, propagate correlation/actor metadata, enforce timeouts, and preserve read/write labels. Tokens come from Databricks App resources or managed identity and must not appear in source, prompts, logs, or trace attributes.

## Error behavior

- Unavailable dependencies fail closed with a structured tool error.
- Invalid approval never degrades to recommendation-as-execution.
- Malformed parser or AI results fail Pydantic validation.
- Timeouts and rate limits are classified for bounded recovery planning.
- Secrets are redacted from structured logging.
- Full source content is not returned unless an explicitly governed path requires it.
