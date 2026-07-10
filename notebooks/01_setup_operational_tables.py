# Databricks notebook source
# MAGIC %md
# MAGIC # Source Readiness operational tables

# COMMAND ----------

catalog = spark.conf.get("source_readiness.catalog")
schema = spark.conf.get("source_readiness.operations_schema")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

# COMMAND ----------

for table, ddl in {
    "source_configuration": "source_id STRING, environment STRING, active_version INT, updated_at TIMESTAMP",
    "configuration_version": "proposal_id STRING, source_id STRING, environment STRING, version INT, parent_version INT, configuration_json STRING, active BOOLEAN, created_at TIMESTAMP",
    "source_assessment": "assessment_id STRING, source_id STRING, readiness_score DOUBLE, readiness_status STRING, assessment_json STRING, assessed_at TIMESTAMP",
    "configuration_proposal": "proposal_id STRING, source_id STRING, version INT, validation_status STRING, proposal_json STRING, created_at TIMESTAMP",
    "sample_run": "sample_run_id STRING, proposal_id STRING, status STRING, result_json STRING, created_at TIMESTAMP",
    "audit_events": "correlation_id STRING, actor STRING, event_type STRING, evidence_json STRING, event_time TIMESTAMP",
}.items():
    spark.sql(f"CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{table} ({ddl}) USING DELTA")
