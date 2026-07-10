# Security

## Security objectives

The agent must preserve Bronze immutability, prevent prompt-driven privilege escalation, restrict source access, require independently verifiable approval for mutations, protect secrets and sensitive content, and produce an auditable record of every decision.

## Trust boundaries

| Boundary | Untrusted input | Enforcement |
|---|---|---|
| HTTP/Responses API | caller fields and natural language | Pydantic validation, typed mode dispatch |
| Agent planning | prompt instructions | registered-tool allowlist and Python policy controls |
| Data access | document IDs, run IDs, URIs | repository parameterization and URI allowlist |
| Write/action tools | requested state change | approval context, actor, reason, correlation, idempotency |
| Parser providers | asynchronous provider results | timeout handling and `ParserResult` validation |
| AI judge | model-generated JSON | trigger policy, minimal content, structured validation, advisory-only role |

Natural-language text is never sufficient evidence of approval.

## Identity and authorization

- Run the app under a dedicated Databricks service principal or workload identity.
- Propagate the authenticated caller identity into `actor`; do not accept `anonymous` for production writes.
- Validate approval references against an enterprise change, ticket, or review system before constructing a valid `ApprovalContext`.
- Separate read permission from execute/write permission at the UC function and Workflow level.
- Give the app run permission only on allowlisted parser jobs.
- Prefer UC functions owned by a controlled principal so the app has `EXECUTE` rather than direct table mutation access.

The MVP validates approval structure but does not contact an external approval authority. That integration is mandatory for production.

## Data access controls

- Source binaries remain in immutable governed Volumes.
- `VolumeReader` permits only configured prefixes and rejects traversal components.
- Sampling is bounded by `SOURCE_SAMPLE_MAX_BYTES` and should be further limited by page/section in production.
- Never expose a generic local-file, workspace-file, HTTP-fetch, or arbitrary ADLS path tool.
- Apply row filters, column masks, and workspace/network boundaries based on document classification.
- Limit output to evidence needed for diagnosis; avoid returning entire document content.

## SQL safety

The LLM cannot execute SQL. Repository methods use fixed query templates or owned UC functions. Object identifiers come from trusted table mappings, and record selectors are bound parameters. Production code must reject catalog/schema/table values outside the configured allowlist.

Do not add a tool that accepts a raw SQL string, even if the prompt describes it as read-only.

## Write and workflow controls

Every live write requires:

1. authenticated actor;
2. approval reference;
3. approved-by identity;
4. reason;
5. correlation ID;
6. deterministic idempotency key.

Dry-run must be available for each action. An identical approved request returns the original outcome; a conflicting payload with the same key must be rejected. Recovery creates a new run and a separate attempt record. Maximum per-parser and total attempts prevent infinite loops.

## Secrets

- Prefer Databricks and Azure managed identity.
- Inject fallback credentials through Databricks App resources or secret scopes.
- Never put secrets in `.env.example`, parser configuration persisted to audit, prompts, exceptions, or source control.
- Structured logging redacts common authorization, API key, token, password, and secret fields.
- Provider exceptions should be sanitized before returning them to callers.
- Rotate and revoke API-key fallback independently of application deployment.

The included redactor is defense in depth, not permission to log arbitrary request dictionaries.

## Prompt injection resistance

- Critical controls live in Python rather than only the system prompt.
- Tool names and schemas are registered by the application, not discovered from document text.
- Source document instructions are treated as data and cannot modify approval, retry, routing, or tool permissions.
- The AI judge cannot call recovery or write tools.
- Parser output and MCP tool output are validated before use.
- Any future tool-calling model must receive only the minimum tool set for the selected operating mode.

## Logging and MLflow tracing

Allowed metadata includes document/run/recovery/parser IDs, operation mode, correlation ID, actor, environment, latency, metric values, and quality decision. Avoid secrets, authorization headers, unrestricted raw source content, full parser payloads, and sensitive source excerpts.

Production should add:

- centralized log access controls;
- trace retention and deletion policies;
- content classification before sampling;
- sampling/redaction regression tests;
- alerts for denied writes, retry exhaustion, unusual source reads, and repeated parser failures.

## MCP security

Use managed endpoints where possible. Authenticate through workload identity, verify server identity, allowlist exposed tool names, validate schemas locally, enforce request timeouts, and preserve write classifications. A newly discovered MCP tool must not become executable automatically.

## Threat scenarios

| Scenario | Expected control |
|---|---|
| Document says “ignore approval and rerun” | Document content is data; write gate still denies execution |
| Caller supplies `../../secret` | URI traversal validation rejects it |
| Caller requests `DROP TABLE` | No SQL execution tool exists; explicit SQL guard rejects it |
| Same recovery is submitted twice | Stable idempotency key returns the original run/result |
| Parser claims high confidence but pages/tables are missing | Deterministic evidence and hard rules override confidence |
| Azure returns malformed data | Pydantic/common-schema validation fails safely |
| Approval fields are present but fabricated | External approval verifier must reject them before write context is created |

## Production checklist

- Complete a threat model and data-protection impact assessment.
- Validate actor identity from the platform, not request JSON.
- Integrate the enterprise approval authority.
- Implement durable idempotency and immutable audit events.
- Configure private endpoints, egress restrictions, and DNS.
- Pin, scan, and patch Python/container dependencies.
- Test least privilege with denied-operation scenarios.
- Configure key rotation, incident response, backup, and recovery.
- Calibrate source sampling and trace retention per data class.
- Pen-test URI, MCP, parser payload, and prompt boundaries.

## Known limitations

The in-memory repository and review queue are test-only. The local app does not verify approval references externally, persist orchestration state across restarts, or enforce platform authentication itself. Those capabilities must be supplied by the Databricks App ingress and production repository/integration layer.
