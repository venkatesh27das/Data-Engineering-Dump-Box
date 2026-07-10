# Databricks notebook source
# MAGIC %md
# MAGIC Register reviewed Unity Catalog functions from `resources/uc_functions.sql`. Replace bundle placeholders through deployment configuration; do not accept identifiers or SQL from an agent request.

# COMMAND ----------

raise RuntimeError("Deployment administrator must review and substitute bundle-managed catalog/schema identifiers before registration")
