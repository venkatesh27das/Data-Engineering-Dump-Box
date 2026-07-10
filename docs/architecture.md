# Architecture

The Databricks App exposes fixed structured endpoints and a ResponsesAgent wrapper. Requests enter the orchestrator and are delegated to one service per operating mode. Services depend on protocols/repositories; deterministic skills contain policy decisions; connectors and governed tools isolate external systems.

Landing is append-only. Bronze raw bytes belong in governed Unity Catalog Volumes, never Delta binary columns. Bronze Delta tables register file/source/batch identity, hashes, MIME, ownership, parser configuration, status, retry/DLQ, and lineage. The agent may read sample Silver quality output but cannot publish Silver.

The local repository supports interruption/resume through persisted operation IDs in-process. Production must persist operation state and idempotency keys in Delta with concurrency constraints. State transitions, approvals, allowlists, sampling bounds, and configuration validation remain deterministic Python controls.
