# Tool contracts

Read tools: `get_document_context`, `get_bronze_manifest`, `get_parser_run`, `get_silver_document`, `get_silver_elements`, `get_quality_assessment`, `get_parser_history`, `get_batch_failures`, `get_parser_metrics`, and bounded `read_source_file_sample`.

State-changing tools: `create_recovery_attempt`, `trigger_reprocessing_workflow`, `update_processing_status`, `submit_human_review`, `quarantine_document`, `record_quality_assessment`, `propose_routing_policy`, and `apply_approved_routing_policy`. Every state-changing call accepts `WriteContext` with actor, approval reference, reason, correlation ID, dry-run, and an idempotency key. Implement production calls as parameterized queries or owned UC functions—not arbitrary SQL.

MCP discovery may map managed tools to the same typed contracts. Descriptions must retain READ ONLY or STATE CHANGING labels. The local test path does not depend on MCP.
