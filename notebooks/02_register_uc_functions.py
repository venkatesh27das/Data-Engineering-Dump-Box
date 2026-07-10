# Databricks notebook source
# MAGIC %md
# MAGIC # Register governed UC functions
# MAGIC Review `resources/uc_functions.sql`, substitute bundle variables during deployment, and execute as a function owner. Never expose a free-form SQL tool to the agent.

# COMMAND ----------
catalog = spark.conf.get("processing_quality.catalog")
operations_schema = spark.conf.get("processing_quality.operations_schema")
assert catalog and operations_schema
display(spark.sql(f"SHOW FUNCTIONS IN `{catalog}`.`{operations_schema}`"))
