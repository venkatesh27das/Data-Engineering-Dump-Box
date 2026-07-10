# Databricks notebook source
# MAGIC %md
# MAGIC # Processing Quality Agent operational tables

# COMMAND ----------
catalog = spark.conf.get("processing_quality.catalog", "main")
schema = spark.conf.get("processing_quality.operations_schema", "processing_quality_ops")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")

# COMMAND ----------
spark.sql(f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.quality_assessment (
 assessment_id STRING, document_id STRING, run_id STRING, metrics MAP<STRING,DOUBLE>,
 final_quality_score DOUBLE, issue_flags ARRAY<STRING>, decision STRING, explanation STRING,
 created_at TIMESTAMP) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.recovery_attempt (
 recovery_id STRING, document_id STRING, source_run_id STRING, recovery_run_id STRING,
 strategy STRING, parser_id STRING, parser_config STRING, approval_reference STRING, actor STRING,
 status STRING, before_quality_score DOUBLE, after_quality_score DOUBLE, outcome STRING,
 idempotency_key STRING, created_at TIMESTAMP) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS `{catalog}`.`{schema}`.human_review_queue (
 review_id STRING, document_id STRING, run_id STRING, issue_type STRING, severity STRING,
 issue_summary STRING, evidence ARRAY<STRING>, recommended_action STRING, created_by STRING,
 created_at TIMESTAMP, status STRING) USING DELTA""")
