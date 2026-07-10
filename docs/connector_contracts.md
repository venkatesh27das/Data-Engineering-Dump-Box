# Connector contracts

Every connector is read-only and implements connection validation, bounded object listing, metadata retrieval, bounded sample/range reads, and inventory estimation. Listings must honor maximum objects/pages/time; samples must honor per-file and cumulative bytes. Continuation tokens are opaque. Errors return inaccessible/NOT_READY evidence without guessing.

ADLS uses managed identity/`DefaultAzureCredential`. SharePoint authentication is pluggable through an approved Graph/enterprise provider. SFTP requires strict host-key validation and secret references, never plaintext passwords. API connectors must enforce allowlisted canonical endpoints, redirects, timeouts, pagination, response schema, and payload limits.
