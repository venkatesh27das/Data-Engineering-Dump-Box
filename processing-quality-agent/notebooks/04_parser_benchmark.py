# Databricks notebook source
# MAGIC %md
# MAGIC # Parser benchmark

# COMMAND ----------
from processing_quality_agent.skills.parser_comparison import rank_parsers
sample = [
    {"parser_id": "databricks_primary", "quality": .82, "success": .95, "latency": .9, "cost": .95, "stability": .9},
    {"parser_id": "azure_document_intelligence", "quality": .93, "success": .92, "latency": .7, "cost": .65, "stability": .88},
]
display(spark.createDataFrame([row.model_dump() for row in rank_parsers(sample).rankings]))
