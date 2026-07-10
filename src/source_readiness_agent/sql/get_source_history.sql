SELECT source_id, version, active, created_at FROM IDENTIFIER(:configuration_table) WHERE source_id = :source_id ORDER BY version DESC
