SELECT document_id, current_run_id, processing_status FROM IDENTIFIER(:manifest_table) WHERE document_id = :document_id
