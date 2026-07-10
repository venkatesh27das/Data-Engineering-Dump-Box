# Databricks notebook source
import asyncio
from source_readiness_agent.app import build_runtime
from source_readiness_agent.config import Settings
from source_readiness_agent.models.requests import AssessSourceRequest

runtime = build_runtime(Settings(app_env="local", use_mock_tools=True))
request = AssessSourceRequest.model_validate({"source": {"source_id": "SRC-SMOKE", "source_name": "Synthetic smoke source", "source_type": "MOCK", "source_system": "fixture", "connection_reference": "mock", "source_location": "mock://", "business_owner": "Platform", "technical_owner": "Engineering"}})
display(asyncio.run(runtime.orchestrator.assess_source(request)).model_dump(mode="json"))
