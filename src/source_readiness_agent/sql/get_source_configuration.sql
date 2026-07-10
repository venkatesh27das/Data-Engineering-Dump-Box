SELECT source_id, version, configuration_json FROM IDENTIFIER(:configuration_table) WHERE source_id = :source_id AND active = true
