# Databricks notebook source
# MAGIC %pip install -e ..

# COMMAND ----------
import asyncio
from processing_quality_agent.app import build_orchestrator
from processing_quality_agent.config import Settings
from processing_quality_agent.models.requests import CompareParsersRequest, InvestigateRequest, RecoverRequest

agent = build_orchestrator(Settings(app_env="local", use_mock_tools=True))
display(asyncio.run(agent.investigate(InvestigateRequest(document_id="DOC-102"))).model_dump())
display(asyncio.run(agent.compare(CompareParsersRequest(document_id="DOC-102", parser_candidates=["databricks_primary", "azure_document_intelligence"]))).model_dump())
display(asyncio.run(agent.recover(RecoverRequest(document_id="DOC-102", source_run_id="RUN-101", dry_run=True))).model_dump())
