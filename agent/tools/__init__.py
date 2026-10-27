"""The 11 ResolveAI agent tools (``03-agent.md`` §5), bound to a case context.

``build_tools(ctx)`` returns plain callables whose signatures exclude the context, ready
to be wrapped by the Strands ``@tool`` decorator in the agent factory.
"""

from __future__ import annotations

from ..context import ToolContext
from .actions import create_voucher, execute_refund, request_refund, schedule_redelivery
from .case import escalate_to_human, update_case
from .messaging import send_message, send_resolution_notice
from .orders import find_orders_by_customer, get_order
from .policy_search import search_policy
from .registry import ToolFn, bind_tool

__all__ = ["TOOL_FUNCTIONS", "TOOL_NAMES", "build_tools"]

TOOL_FUNCTIONS: tuple[ToolFn, ...] = (
    get_order,
    find_orders_by_customer,
    search_policy,
    update_case,
    send_message,
    create_voucher,
    schedule_redelivery,
    request_refund,
    execute_refund,
    escalate_to_human,
    send_resolution_notice,
)

TOOL_NAMES: tuple[str, ...] = tuple(fn.__name__ for fn in TOOL_FUNCTIONS)


def build_tools(ctx: ToolContext) -> list[ToolFn]:
    """Bind every tool to ``ctx`` (one context per agent turn)."""
    return [bind_tool(fn, ctx) for fn in TOOL_FUNCTIONS]
