-- Illustrative governed Unity Catalog SQL functions. Replace logical tables through deployment variables.
CREATE OR REPLACE FUNCTION ${catalog}.${operations_schema}.get_document_processing_context(p_document_id STRING)
RETURNS TABLE(document_id STRING, current_run_id STRING, processing_status STRING)
RETURN SELECT document_id, current_run_id, processing_status
FROM ${catalog}.${bronze_schema}.bronze_file_manifest
WHERE document_id = p_document_id;

CREATE OR REPLACE FUNCTION ${catalog}.${operations_schema}.get_parser_history(p_document_id STRING)
RETURNS TABLE(run_id STRING, parser_id STRING, parser_version STRING, status STRING, latency_ms BIGINT)
RETURN SELECT run_id, parser_id, parser_version, status, latency_ms
FROM ${catalog}.${operations_schema}.parser_run
WHERE document_id = p_document_id;

-- Writes should be procedures/functions owned by a service principal and validate actor,
-- approval_reference, reason, correlation_id, and idempotency_key before MERGE/INSERT.
