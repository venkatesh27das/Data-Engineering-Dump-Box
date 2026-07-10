SELECT document_id, current_run_id, processing_status FROM IDENTIFIER(:manifest_table) WHERE ingestion_batch_id = :batch_id AND processing_status = 'QUALITY_FAILED'
