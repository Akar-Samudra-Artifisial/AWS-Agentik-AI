"""Request/response schemas for the dashboard API (``02-backend.md`` §5, §6).

These drive the generated OpenAPI document (BE-016) consumed by the dashboard.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from resolveai_common.models import (
    AgentEvent,
    Approval,
    Case,
    CaseCategory,
    CasePriority,
    CaseStatus,
    Channel,
    Customer,
    Message,
    Order,
    ResolutionType,
)

__all__ = [
    "ApprovalWithCase",
    "CaseDetail",
    "CaseSummary",
    "DecisionRequest",
    "DecisionResponse",
    "DemoResetDeleted",
    "DemoResetResponse",
    "ErrorBody",
    "ErrorResponse",
    "HealthResponse",
    "Metrics",
    "SimulateInboundRequest",
    "SimulateInboundResponse",
]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CaseSummary(BaseModel):
    case_id: str
    status: CaseStatus
    category: CaseCategory
    priority: CasePriority
    channel: Channel
    customer_name: str | None = None
    order_id: str | None = None
    summary: str = ""
    created_at: str
    updated_at: str
    resolution_type: ResolutionType | None = None
    resolution_summary: str | None = None


class CaseDetail(BaseModel):
    case: Case
    customer: Customer | None = None
    order: Order | None = None
    messages: list[Message]
    events: list[AgentEvent]
    approvals: list[Approval]


class ApprovalWithCase(Approval):
    case: CaseSummary | None = None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)
    decided_by: str = Field(min_length=1, max_length=100)


class DecisionResponse(BaseModel):
    approval_id: str
    status: Literal["approved", "rejected"]


class SimulateInboundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Channel
    from_e164: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=2000)


class SimulateInboundResponse(BaseModel):
    event_id: str
    case_id: str | None = None


class DemoResetDeleted(BaseModel):
    cases: int = 0
    messages: int = 0
    agent_events: int = 0
    approvals: int = 0


class DemoResetResponse(BaseModel):
    deleted: DemoResetDeleted
    reset_orders: list[str]


class Totals(BaseModel):
    cases: int = 0
    active: int = 0
    resolved: int = 0
    escalated: int = 0
    pending_approvals: int = 0


class FirstResponseMs(BaseModel):
    p50: int = 0
    p90: int = 0


class ResolutionMs(BaseModel):
    p50: int = 0


class Metrics(BaseModel):
    totals: Totals
    auto_resolution_rate: float
    first_response_ms: FirstResponseMs
    resolution_ms: ResolutionMs
    by_channel: dict[str, int]
    by_category: dict[str, int]
    messages_sent: dict[str, int]
