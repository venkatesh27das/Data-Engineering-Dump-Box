# Operations runbook

## Purpose

This runbook covers investigation, approved recovery, parser comparison, routing-policy proposals, incident response, and common service failures. Always retain the correlation ID and avoid copying sensitive document content into tickets.

## Health checks

```bash
curl -s https://APP_HOST/health
curl -s https://APP_HOST/ready
```

`/health` confirms the web process is alive. `/ready` currently confirms application startup; production should extend readiness to verify the governed repository, required UC functions, Workflow job configuration, MLflow availability, and enabled parser health.

## Investigating a quality failure

1. Identify `document_id`, current/source `run_id`, ingestion batch, and caller identity.
2. Call `POST /api/v1/investigate` with `dry_run=true`.
3. Record the response correlation ID.
4. Review metric evidence, hard failures, parser warnings/errors, and history.
5. Confirm the diagnosed failure maps to observed evidence.
6. If the evidence is insufficient, request a bounded source sample or human review; do not assume.
7. Choose the recommended action or document why an alternative governed strategy is safer.

Example:

```bash
curl -s https://APP_HOST/api/v1/investigate \
  -H 'content-type: application/json' \
  -d '{
    "document_id":"DOC-102",
    "question":"Why did table extraction fail?",
    "include_source_sample":false,
    "dry_run":true,
    "actor":"engineer@example.com"
  }'
```

## Dry-run recovery

Use dry-run to validate the selected strategy, parser, retry limits, and idempotency inputs without writing or triggering a job.

```bash
curl -s https://APP_HOST/api/v1/recover \
  -H 'content-type: application/json' \
  -d '{
    "document_id":"DOC-102",
    "source_run_id":"RUN-101",
    "strategy":"RETRY_WITH_ALTERNATE_PARSER",
    "preferred_parser_id":"azure_document_intelligence",
    "actor":"engineer@example.com",
    "dry_run":true
  }'
```

Expected result: a recovery plan and `DRY_RUN` execution status, with no recovery record and no production workflow run.

## Approved live recovery

Before execution, obtain an externally verifiable approval reference. Confirm the actor, approver, reason, target document/run, parser/configuration, estimated cost, and policy attempt limits.

```bash
curl -s https://APP_HOST/api/v1/recover \
  -H 'content-type: application/json' \
  -d '{
    "document_id":"DOC-102",
    "source_run_id":"RUN-101",
    "strategy":"RETRY_WITH_ALTERNATE_PARSER",
    "preferred_parser_id":"azure_document_intelligence",
    "approval":{
      "approved":true,
      "approval_reference":"CHG-12345",
      "approved_by":"approver@example.com"
    },
    "reason":"Recover missing policy tables",
    "actor":"engineer@example.com",
    "dry_run":false
  }'
```

Verify:

- new workflow run ID exists;
- workflow reached a terminal status;
- recovery run differs from the source run;
- before/after scores and `IMPROVED`, `UNCHANGED`, or `REGRESSED` outcome are recorded;
- final quality decision matches evidence;
- `create_recovery_attempt` appears in the tool audit;
- no previous parser output or source file changed.

If approval is missing, the expected status is `AWAITING_APPROVAL` and no workflow run ID should exist.

## Parser comparison

Use representative samples and declare the optimization profile. Results are recommendations and must not modify production routing.

```bash
curl -s https://APP_HOST/api/v1/compare-parsers \
  -H 'content-type: application/json' \
  -d '{
    "document_id":"DOC-102",
    "parser_candidates":["databricks_primary","azure_document_intelligence"],
    "quality_weight_profile":"BALANCED",
    "execute_missing":false,
    "dry_run":true,
    "actor":"engineer@example.com"
  }'
```

Check component quality, success, latency, cost, and stability scores. Investigate sample bias and warning/failure distribution before accepting the top-ranked parser.

## Policy optimization

Call `POST /api/v1/optimize-policy` with a document class, allowed parsers, current policy, sample IDs, and profile. First request `apply=false` and review the proposed YAML. Applying a policy requires valid approval and must create a versioned policy/audit record in the production repository.

## Operation lookup

```bash
curl -s https://APP_HOST/api/v1/operations/CORRELATION_ID
```

The local operation store is process memory. A 404 after restart is expected in the MVP; production must persist state.

## Failure handling

### Repository unavailable

- Stop live recovery and policy application.
- Confirm app identity, UC grants, warehouse/function availability, and configured mappings.
- Do not switch to mock mode in a production app.
- Record the correlation ID and restore the governed dependency.

### Workflow trigger fails

- Check parser-to-job mapping and run permission.
- Search for an existing run with the same idempotency key before retrying.
- Do not submit a second manual run blindly.
- Classify configuration errors separately from transient service errors.

### Workflow timeout

- Inspect the Databricks job run and parser provider health.
- Cancel only when the run is known to be safe to cancel.
- Record `PARSER_TIMEOUT`; follow bounded retry policy.
- Escalate after retry exhaustion.

### Azure rate limit or outage

- Confirm 429/service status without logging credentials or document payloads.
- Respect provider retry guidance and concurrency limits.
- Use an alternate parser only when eligibility, cost, and policy permit it.

### Quality regresses after recovery

- Do not publish the recovery run merely because the workflow succeeded.
- Keep the previous run immutable and reference both runs in the attempt.
- Compare metric evidence to identify regression dimensions.
- Route to alternate parser or human review within attempt limits.

### Corrupt or unsupported file

- Corrupt source: quarantine and escalate; do not loop parsers.
- Unsupported format: reject with a clear eligibility explanation.
- Never alter the source file to make it parseable; any transformed derivative is a new governed artifact.

### Confidence disagreement

- Compare normalized confidence with deterministic page/text/table/layout evidence.
- Trigger AI judgment only when policy permits and provide minimal evidence.
- AI output remains advisory and cannot execute recovery.

## Human review

The review request includes document/run, issue type and severity, summary, evidence, source references, recommendation, parser comparison, creator, timestamp, and status. The MVP queue is in memory; production must use Delta or an external review service. Avoid attaching unrestricted source content to the review record.

## Observability

Search structured logs and MLflow traces using correlation ID, then document/run/recovery ID. Validate state history and invoked tools before interpreting a failure. Never paste authorization headers, API keys, full document text, or raw provider payloads into incidents.

Recommended alerts:

- approval-denied write attempts;
- parser failure/rate-limit/timeout spikes;
- retry exhaustion;
- quarantine volume increase;
- source access rejection;
- quality score distribution shift;
- trace or audit persistence failure.

## Rollback and containment

- Disable unsafe parser eligibility or Workflow permission.
- Restore the previous routing-policy version.
- Roll back app code using the bundle release process.
- Preserve all source files, parser runs, quality assessments, and recovery attempts.
- If sensitive content was traced, follow the data incident process and trace-retention controls.

## Escalation information

Provide correlation ID, document/run IDs, parser ID/version, failure category, deterministic metrics, workflow run ID, approval reference (not secret), retry history, and current state. Do not include credentials or unrestricted document content.
