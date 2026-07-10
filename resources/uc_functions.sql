-- Illustrative governed functions. Replace identifiers at deployment; do not expose arbitrary SQL.
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.get_source_configuration(p_source_id STRING)
RETURNS TABLE(source_id STRING, version INT, configuration_json STRING)
RETURN SELECT source_id, version, configuration_json
FROM ${catalog}.${schema}.source_configuration
WHERE source_id = p_source_id;

CREATE OR REPLACE FUNCTION ${catalog}.${schema}.get_configuration_history(p_source_id STRING)
RETURNS TABLE(source_id STRING, version INT, active BOOLEAN, created_at TIMESTAMP)
RETURN SELECT source_id, version, active, created_at
FROM ${catalog}.${schema}.configuration_version
WHERE source_id = p_source_id;
