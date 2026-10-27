"""Result helpers, ``ToolError`` and ``agent_events`` writer shared by every tool."""

from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError
from resolveai_common.logging import get_logger
from resolveai_common.models import AgentEvent, AgentEventType

from ..context import ToolContext
from ..guards import Violation

__all__ = [
    "EVENT_MAX_BYTES",
    "ToolError",
    "fail",
    "ok",
    "record_event",
    "to_json",
    "truncate_utf8",
]

# agent_events.input/output are capped at 4 KB (AG-003).
EVENT_MAX_BYTES = 4096


class ToolError(Exception):
    """Raised inside a tool; converted by ``logged_tool`` into a structured error result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @classmethod
    def from_violation(cls, violation: Violation) -> ToolError:
        return cls(violation.code, violation.message)


def ok(**data: Any) -> dict[str, Any]:
    return {"ok": True, **data}


def fail(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def truncate_utf8(text: str | None, limit: int = EVENT_MAX_BYTES) -> str | None:
    """Cut ``text`` to at most ``limit`` UTF-8 bytes without splitting a character."""
    if text is None:
        return None
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", errors="ignore")


def record_event(
    ctx: ToolContext,
    event_type: AgentEventType,
    *,
    tool: str | None = None,
    input_text: str | None = None,
    output_text: str | None = None,
    latency_ms: int | None = None,
    success: bool = True,
) -> None:
    """Persist one timeline event; a write failure is logged, never raised to the agent."""
    try:
        ctx.repos.agent_events.put(
            AgentEvent(
                case_id=ctx.case_id,
                ts=ctx.now_iso(),
                seq=ctx.next_seq(),
                type=event_type,
                tool=tool,
                input=truncate_utf8(input_text),
                output=truncate_utf8(output_text),
                latency_ms=latency_ms,
                ok=success,
            )
        )
    except (BotoCoreError, ClientError, ValidationError) as exc:
        get_logger(__name__, ctx.case_id).warning(
            "agent_event write failed", extra={"tool": tool, "error": str(exc)}
        )
