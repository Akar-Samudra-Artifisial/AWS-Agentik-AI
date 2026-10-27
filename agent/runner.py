"""One agent turn: parse the ``02-backend.md`` §8 payload, run the agent, build the response.

Shared by the AgentCore entrypoint (``app.py``) and the Lambda fallback
(``lambda_handler.py``). ``run_turn`` never raises: invalid payloads and runtime failures
are returned as ``{..., "error": "<code>: <detail>"}`` so the dispatcher runs its
fail-safe (``02-backend.md`` §7).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from resolveai_common.logging import get_logger
from resolveai_common.models import AgentEventType, Channel

from .config import get_optional_param
from .context import ToolContext
from .tools.base import ToolError, fail, record_event, to_json
from .tools.messaging import send_message
from .tools.policy_search import BedrockKnowledgeBaseRetriever

__all__ = [
    "AgentBuilder",
    "ContextFactory",
    "InvocationPayload",
    "build_prompt",
    "default_context_factory",
    "run_turn",
]

HISTORY_LIMIT = 20
REPLY_FALLBACK = "reply_fallback"
REPLY_NUDGE = (
    "Kamu belum membalas pelanggan pada giliran ini. Kirim balasan sekarang via "
    "send_message (atau send_resolution_notice bila kasus sudah selesai)."
)
REPLY_FALLBACK_ID = (
    "Terima kasih, pesan Anda sudah kami terima dan sedang kami proses. "
    "Kami akan segera mengabari Anda."
)
REPLY_FALLBACK_EN = (
    "Thank you, we have received your message and are working on it. "
    "We will update you shortly."
)
_LENIENT = ConfigDict(extra="ignore")


class CustomerPayload(BaseModel):
    model_config = _LENIENT

    customer_id: str = ""
    name: str = ""
    language: str = "id"
    preferred_channel: str | None = None


class MessagePayload(BaseModel):
    model_config = _LENIENT

    text: str = Field(max_length=4000)
    received_at: str = ""


class HistoryItem(BaseModel):
    model_config = _LENIENT

    direction: str
    author: str = ""
    channel: str = ""
    body: str = ""
    ts: str = ""


class ApprovalPayload(BaseModel):
    model_config = _LENIENT

    approval_id: str = Field(pattern=r"^APR-")
    status: Literal["approved", "rejected"]
    note: str = ""


class InvocationPayload(BaseModel):
    """Agent invocation contract (``02-backend.md`` §8)."""

    model_config = _LENIENT

    event_type: Literal["customer_message", "approval_decided"]
    case_id: str = Field(pattern=r"^CASE-")
    customer: CustomerPayload = Field(default_factory=CustomerPayload)
    channel: str = "whatsapp"
    message: MessagePayload | None = None
    history: list[HistoryItem] = Field(default_factory=list)
    approval: ApprovalPayload | None = None

    @model_validator(mode="after")
    def _event_fields(self) -> InvocationPayload:
        if self.event_type == "customer_message" and self.message is None:
            raise ValueError("customer_message requires message")
        if self.event_type == "approval_decided" and self.approval is None:
            raise ValueError("approval_decided requires approval")
        return self


class TurnAgent(Protocol):
    """The part of ``strands.Agent`` used here: call with a prompt, get a result."""

    def __call__(self, prompt: str) -> Any: ...


ContextFactory = Callable[[str], ToolContext]
AgentBuilder = Callable[[ToolContext, list[dict[str, Any]]], TurnAgent]


def _data(text: str) -> str:
    # Customer text cannot open/close the prompt's data tags.
    return text.replace("<", "‹").replace(">", "›")


def build_prompt(payload: InvocationPayload) -> str:
    """Render the turn input; customer-authored text is fenced as data (rule 5)."""
    lines = [
        f"event_type: {payload.event_type}",
        f"kanal: {payload.channel}",
        (
            f"pelanggan: nama={_data(payload.customer.name) or '-'}, "
            f"bahasa={payload.customer.language}"
        ),
    ]
    history = payload.history[-HISTORY_LIMIT:]
    if history:
        lines.append("<riwayat>")
        lines.extend(
            f"[{h.ts}] {h.direction}/{h.author or '-'} ({h.channel or '-'}): {_data(h.body)}"
            for h in history
        )
        lines.append("</riwayat>")
    if payload.message is not None:
        lines += [
            "<pesan_pelanggan>",
            _data(payload.message.text),
            "</pesan_pelanggan>",
        ]
    if payload.approval is not None:
        approval = payload.approval
        lines += [
            "<keputusan_approval>",
            f"approval_id: {approval.approval_id}",
            f"status: {approval.status}",
            f"catatan staf: {_data(approval.note) or '-'}",
            "</keputusan_approval>",
        ]
    return "\n".join(lines)


def default_context_factory(case_id: str) -> ToolContext:
    """Real DynamoDB + AWS senders; KB retrieval only when ``kb/id`` is configured."""
    kb_id = get_optional_param("kb/id", "KNOWLEDGE_BASE_ID")
    retriever = BedrockKnowledgeBaseRetriever(kb_id) if kb_id else None
    return ToolContext.create(case_id, policy_retriever=retriever)


def _default_agent_builder(
    ctx: ToolContext, actions: list[dict[str, Any]]
) -> TurnAgent:
    from .agent_factory import build_agent  # strands is imported only when needed

    return build_agent(ctx, actions)


def _send_reply_fallback(
    ctx: ToolContext, actions: list[dict[str, Any]], language: str
) -> bool:
    """Send the fixed holding reply through the ``send_message`` path; log ``reply_fallback``."""
    text = REPLY_FALLBACK_EN if language == "en" else REPLY_FALLBACK_ID
    record_event(
        ctx,
        AgentEventType.TOOL_CALL,
        tool=REPLY_FALLBACK,
        input_text=to_json({"body": text}),
    )
    try:
        # Unwrapped: the fallback must not count against the model's tool-call budget.
        result = inspect.unwrap(send_message)(ctx, body=text)
    except ToolError as exc:
        result = fail(exc.code, exc.message)
    sent = bool(result.get("ok"))
    record_event(
        ctx,
        AgentEventType.TOOL_RESULT,
        tool=REPLY_FALLBACK,
        output_text=to_json(result),
        success=sent,
    )
    actions.append({"tool": REPLY_FALLBACK, "ok": sent})
    return sent


def _ensure_reply(
    ctx: ToolContext,
    agent: TurnAgent,
    result: Any,
    actions: list[dict[str, Any]],
    payload: InvocationPayload,
    log: Any,
) -> Any:
    """Every customer message gets a reply: one nudge, then a deterministic fallback."""
    if ctx.delivered:
        return result
    log.warning("agent did not reply; nudging")
    result = agent(REPLY_NUDGE)
    if ctx.delivered:
        return result
    sent = _send_reply_fallback(ctx, actions, payload.customer.language)
    log.warning("agent still silent; reply fallback", extra={"sent": sent})
    return result


def _response(
    case_id: str | None,
    actions: list[dict[str, Any]],
    *,
    case_status: str | None = None,
    category: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "case_status": case_status,
        "category": category,
        "actions": actions,
        "error": error,
    }


def run_turn(
    raw: Any,
    *,
    context_factory: ContextFactory = default_context_factory,
    agent_builder: AgentBuilder = _default_agent_builder,
) -> dict[str, Any]:
    """Run one agent turn and return ``{case_id, case_status, category, actions, error}``."""
    raw_case_id = raw.get("case_id") if isinstance(raw, dict) else None
    case_id = raw_case_id if isinstance(raw_case_id, str) else None
    actions: list[dict[str, Any]] = []
    log = get_logger(__name__, case_id)
    try:
        payload = InvocationPayload.model_validate(raw)
    except ValidationError as exc:
        fields = sorted(
            {".".join(map(str, e["loc"])) or "payload" for e in exc.errors()}
        )
        log.warning("invalid invocation payload", extra={"fields": fields})
        return _response(
            case_id, actions, error=f"invalid_payload: {', '.join(fields)}"
        )

    try:
        ctx = context_factory(payload.case_id)
        if ctx.repos.cases.get(payload.case_id) is None:
            return _response(payload.case_id, actions, error="case_not_found")
        if payload.event_type == "customer_message" and payload.channel in set(Channel):
            ctx.inbound_channel = Channel(payload.channel)
        agent = agent_builder(ctx, actions)
        result = agent(build_prompt(payload))
        if payload.event_type == "customer_message":
            result = _ensure_reply(ctx, agent, result, actions, payload, log)
        record_event(
            ctx, AgentEventType.MODEL_MESSAGE, output_text=to_json(str(result).strip())
        )
        case = ctx.repos.cases.get(payload.case_id)
    except Exception as exc:  # the dispatcher needs a response, not a crash
        log.exception("agent turn failed", extra={"event_type": payload.event_type})
        return _response(
            payload.case_id, actions, error=f"agent_error: {type(exc).__name__}: {exc}"
        )

    log.info(
        "agent turn finished",
        extra={"event_type": payload.event_type, "tool_calls": len(actions)},
    )
    if case is None:
        return _response(payload.case_id, actions, error="case_not_found")
    return _response(
        payload.case_id,
        actions,
        case_status=case.status.value,
        category=case.category.value,
    )
