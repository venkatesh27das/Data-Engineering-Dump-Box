# Security

The App is read-only by default. Pydantic rejects unknown fields and unsafe schemes/traversal. Connectors enforce allowlists and bounds. No arbitrary SQL/Python/shell tools exist. File content is untrusted. Configuration activation is both approval-gated and feature-flagged. Logs recursively redact common secret keys/patterns, and traces exclude content/credentials.

Production still requires authenticated API ingress, authorization by source/environment, canonical endpoint verification, private networking/egress policy, a trusted approval verifier, distributed idempotency, UC/ADLS least privilege, rate limiting, archive/malformed-file defenses, audit export, retention, and penetration testing.
