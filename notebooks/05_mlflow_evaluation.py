# Databricks notebook source
# MAGIC %md
# MAGIC # MLflow evaluation seed dataset

# COMMAND ----------
import mlflow
rows = [
    {"document_id": "SYNTH-MISSING-TABLE", "expected_failure": "TABLE_EXTRACTION_FAILURE", "expected_action": "TABLE_FOCUSED_REPROCESS"},
    {"document_id": "SYNTH-TIMEOUT", "expected_failure": "PARSER_TIMEOUT", "expected_action": "RETRY_SAME_CONFIGURATION"},
]
evaluation_df = spark.createDataFrame(rows)
display(evaluation_df)
# Configure a logged ResponsesAgent model, then pass it to mlflow.evaluate with custom
# scorers for diagnosis accuracy, tool selection, and recovery recommendation quality.
