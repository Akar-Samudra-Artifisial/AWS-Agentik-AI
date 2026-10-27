"""``logged_tool`` decorator and ``bind_tool``: budget, validation, logging, ctx binding.

Tool implementations are written as ``fn(ctx, **params) -> dict``. ``logged_tool``
wraps them to:
  - enforce ``MAX_TOOL_CALLS_PER_TURN`` (excess calls are refused and the case is
    escalated once, AG-006);
  - validate arguments strictly against the annotations (pydantic, no coercion);
  - record ``tool_call`` / ``tool_result`` events with latency to ``agent_events``,
    output truncated to 4 KB (AG-003);
  - convert ``ToolError`` and unexpected exceptions into ``{ok: false, error}``.

``bind_tool`` closes over a ``ToolContext`` and exposes a signature without ``ctx`` so
the model only ever sees business parameters (never a recipient or case id).
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError
from resolveai_common import policy
from resolveai_common.logging import get_logger
from resolveai_common.models import AgentEventType, CasePriority

from ..context import ToolContext
from .base import ToolError, fail, record_event, to_json
from .core import escalate_case

__all__ = ["ToolFn", "auto_escalate", "bind_tool", "logged_tool"]

ToolFn = Callable[..., dict[str, Any]]


def auto_escalate(ctx: ToolContext, reason: str, *, notify: bool) -> None:
    """Escalate the case once per turn when a hard limit is hit (AG-006)."""
    if ctx.auto_escalated:
        return
    ctx.auto_escalated = True
    try:
        escalate_case(ctx, reason, CasePriority.NORMAL, notify=notify)
    except ToolError as exc:
        get_logger(__name__, ctx.case_id).warning(
            "auto escalation skipped", extra={"reason": reason, "error": exc.message}
        )


def _validate(
    fn: ToolFn, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Bind and strictly validate ``args``/``kwargs`` against ``fn`` (minus ``ctx``)."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())[1:]
    try:
        bound = sig.replace(parameters=params).bind(*args, **kwargs)
    except TypeError as exc:
        raise ToolError("invalid_input", str(exc)) from exc
    bound.apply_defaults()
    for name, value in bound.arguments.items():
        annotation = sig.parameters[name].annotation
        if annotation is inspect.Parameter.empty:
            continue
        try:
            TypeAdapter(annotation).validate_python(value, strict=True)
        except ValidationError as exc:
            raise ToolError("invalid_input", f"parameter {name} tidak valid") from exc
    return dict(bound.arguments)


def logged_tool(fn: ToolFn) -> ToolFn:
    """Decorate a tool implementation ``fn(ctx, **params)``; see module docstring."""

    @functools.wraps(fn)
    def wrapper(ctx: ToolContext, *args: Any, **kwargs: Any) -> dict[str, Any]:
        name = fn.__name__
        record_event(
            ctx,
            AgentEventType.TOOL_CALL,
            tool=name,
            input_text=to_json({"args": list(args), **kwargs} if args else kwargs),
        )
        start = time.perf_counter()
        ctx.tool_calls += 1
        try:
            if ctx.tool_calls > policy.MAX_TOOL_CALLS_PER_TURN:
                auto_escalate(
                    ctx, "batas tool call per giliran terlampaui", notify=True
                )
                raise ToolError(
                    "tool_limit_exceeded",
                    f"batas {policy.MAX_TOOL_CALLS_PER_TURN} tool call per giliran tercapai; "
                    "kasus sudah dieskalasi, akhiri giliran",
                )
            result = fn(ctx, **_validate(fn, args, kwargs))
        except ToolError as exc:
            result = fail(exc.code, exc.message)
        except Exception:  # noqa: BLE001 - the agent must always get a structured result
            get_logger(__name__, ctx.case_id).exception(
                "tool failed", extra={"tool": name}
            )
            result = fail("internal_error", f"{name} gagal karena kesalahan internal")
        latency_ms = int((time.perf_counter() - start) * 1000)
        record_event(
            ctx,
            AgentEventType.TOOL_RESULT,
            tool=name,
            output_text=to_json(result),
            latency_ms=latency_ms,
            success=bool(result.get("ok")),
        )
        return result

    return wrapper


def bind_tool(fn: ToolFn, ctx: ToolContext) -> ToolFn:
    """Return ``fn`` bound to ``ctx`` with ``ctx`` removed from the public signature."""
    target = inspect.unwrap(fn)
    sig = inspect.signature(target)
    public = sig.replace(parameters=list(sig.parameters.values())[1:])

    def bound(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return fn(ctx, *args, **kwargs)

    bound.__name__ = target.__name__
    bound.__qualname__ = target.__name__
    bound.__doc__ = target.__doc__
    bound.__module__ = target.__module__
    bound.__signature__ = public  # type: ignore[attr-defined]
    bound.__annotations__ = {
        k: v for k, v in getattr(target, "__annotations__", {}).items() if k != "ctx"
    }
    return bound
