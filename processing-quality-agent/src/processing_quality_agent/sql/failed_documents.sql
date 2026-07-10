SELECT document_id, current_run_id, processing_status FROM IDENTIFIER(:manifest_table) WHERE processing_status = 'QUALITY_FAILED' LIMIT :limit
