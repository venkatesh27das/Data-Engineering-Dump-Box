# Security

- Use a dedicated service principal with read access to required Bronze/Silver objects and execute permission on narrowly scoped UC functions.
- Grant workflow run permission only to the app identity. Validate actor and approval server-side; do not trust prompt text.
- Allowlist UC Volume and ADLS prefixes, limit samples, reject traversal, redact secrets, and disable sensitive content tracing by default.
- Store Azure credentials in Databricks resources/secrets or use managed identity. API-key auth is an explicit fallback.
- The MVP in-memory repository is not suitable for production; bind audited Delta/UC implementations before setting `USE_MOCK_TOOLS=false`.
