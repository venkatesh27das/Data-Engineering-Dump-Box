# Configuration contracts

Proposals combine source identity, landing, ingestion, Bronze registration, parser routing, metadata, and workflow parameters. They are disabled until approved activation. Paths are environment-separated and landing/checkpoint/schema/quarantine locations are distinct. Raw bytes remain in UC Volumes; manifest mappings are explicit.

Every version stores proposal/source/environment/version/parent, change summary, generator/reviewer/approver, approval reference, validation and active state, and timestamps. Approved versions are immutable. A prior version can be rolled back only through the same validated approval and activation path.
