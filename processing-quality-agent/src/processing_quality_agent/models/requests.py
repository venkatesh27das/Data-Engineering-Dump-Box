from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .recovery import ApprovalContext, RecoveryStrategy


class OperationMode(StrEnum):
    INVESTIGATE = "INVESTIGATE"
    RECOVER = "RECOVER"
    COMPARE_PARSERS = "COMPARE_PARSERS"
    OPTIMIZE_POLICY = "OPTIMIZE_POLICY"


class InvestigateRequest(BaseModel):
    document_id: str | None = None
    run_id: str | None = None
    batch_id: str | None = None
    question: str | None = None
    include_source_sample: bool = False
    request_ai_judge: bool = False
    dry_run: bool = True
    actor: str = "anonymous"
    correlation_id: str | None = None

    @model_validator(mode="after")
    def require_selector(self) -> InvestigateRequest:
        if not any((self.document_id, self.run_id, self.batch_id)):
            raise ValueError("one of document_id, run_id, or batch_id is required")
        return self


class RecoverRequest(BaseModel):
    document_id: str
    source_run_id: str
    strategy: RecoveryStrategy | None = None
    preferred_parser_id: str | None = None
    parser_config: dict[str, Any] = Field(default_factory=dict)
    approval: ApprovalContext = Field(default_factory=ApprovalContext)
    reason: str = "quality recovery"
    dry_run: bool = True
    actor: str = "anonymous"
    correlation_id: str | None = None


class CompareParsersRequest(BaseModel):
    document_id: str | None = None
    sample_document_ids: list[str] = Field(default_factory=list)
    parser_candidates: list[str] = Field(min_length=2)
    quality_weight_profile: str = "BALANCED"
    execute_missing: bool = False
    approval: ApprovalContext = Field(default_factory=ApprovalContext)
    dry_run: bool = True
    actor: str = "anonymous"
    correlation_id: str | None = None

    @model_validator(mode="after")
    def require_sample(self) -> CompareParsersRequest:
        if not self.document_id and not self.sample_document_ids:
            raise ValueError("document_id or sample_document_ids is required")
        return self


class OptimizePolicyRequest(BaseModel):
    document_class: str
    sample_document_ids: list[str] = Field(default_factory=list)
    current_routing_policy: dict[str, Any] = Field(default_factory=dict)
    allowed_parser_candidates: list[str] = Field(min_length=1)
    optimization_profile: str = "BALANCED"
    apply: bool = False
    approval: ApprovalContext = Field(default_factory=ApprovalContext)
    dry_run: bool = True
    actor: str = "anonymous"
    correlation_id: str | None = None


class ResponsesInputItem(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class ResponsesAgentRequest(BaseModel):
    input: str | list[ResponsesInputItem]
    custom_inputs: dict[str, Any] = Field(default_factory=dict)
