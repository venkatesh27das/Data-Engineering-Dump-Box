# Runbook

1. Confirm source owner, connection reference, allowlist, expected formats/volume, and metadata requirements.
2. Run `ASSESS_SOURCE`; resolve ACCESS_BLOCKED/NOT_READY blockers without widening access unnecessarily.
3. Generate and validate a proposal. Review landing, checkpoint, Bronze, parser, metadata, retry/DLQ, workflow, environment, and version.
4. Obtain a change reference and verified approval; run a dry sample first, then controlled live sample if permitted.
5. Confirm accounting, registration, parsing, manifest, lineage, and failure classification thresholds.
6. Keep activation disabled until production governance review. Enable briefly through controlled deployment, activate with verified approval, then disable again.
7. Monitor first ingestion, audit events, DLQ, and lineage. Rollback means approved activation of an earlier immutable version.
