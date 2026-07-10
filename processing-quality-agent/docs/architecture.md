# Architecture

The FastAPI/ResponsesAgent layer translates transport contracts only. `AgentOrchestrator` owns explicit state, correlation, evidence, and approval flow. Pure services implement scoring, diagnosis, recovery, comparison, and optimization. Tools isolate reads, approved writes, Databricks Workflows, MCP, and parser-specific SDK calls.

Bronze binaries remain immutable in UC Volumes. Delta stores identities, runs, assessments, recovery attempts, and audit records. Each recovery creates a new run ID; no prior Silver output is updated in place.
