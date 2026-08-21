from fastapi import Request

from app.agents.runtime import AgentRuntime
from app.llm.model_registry import ModelRegistry
from app.services.intake_service import IntakeService
from app.services.run_processor import RunProcessor
from app.storage.database import Database
from app.storage.local_store import LocalStore


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_store(request: Request) -> LocalStore:
    return request.app.state.store


def get_intake(request: Request) -> IntakeService:
    return request.app.state.intake


def get_processor(request: Request) -> RunProcessor:
    return request.app.state.processor


def get_models(request: Request) -> ModelRegistry:
    return request.app.state.models


def get_agent_runtime(request: Request) -> AgentRuntime:
    return request.app.state.agent_runtime
