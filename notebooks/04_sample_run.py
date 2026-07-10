# Databricks notebook source
# MAGIC %md
# MAGIC Invoke `/api/v1/sample-run` only with a validated proposal and verified approval object. This notebook intentionally does not embed credentials, job IDs, source paths, or approval references.

# COMMAND ----------

dbutils.widgets.text("proposal_id", "")
dbutils.widgets.text("approval_reference", "")
dbutils.widgets.dropdown("dry_run", "true", ["true", "false"])
assert dbutils.widgets.get("proposal_id"), "proposal_id is required"
assert dbutils.widgets.get("approval_reference"), "approval_reference is required"
