"""Shared case/customer access, outbound delivery and escalation used by several tools.

Recipients are always derived here from the case's customer record — never from tool
arguments. Every send attempt (including fallbacks) is persisted to ``messages``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from resolveai_common import policy
from resolveai_common.messaging.dispatch import DEFAULT_FALLBACK_ORDER
from resolveai_common.models import (
    AgentEventType,
    Case,
    CasePriority,
    CaseStatus,
    Channel,
    Customer,
    DeliveryStatus,
    Language,
    Message,
    MessageAuthor,
    MessageDirection,
    Order,
    ResolutionType,
)

from ..context import ToolContext
from ..guards import owns_order, staff_on_duty
from .base import ToolError, record_event, to_json

__all__ = [
    "Attempt",
    "Rendered",
    "consume_outbound",
    "deliver",
    "escalate_case",
    "fallback_chain",
    "load_case",
    "load_customer",
    "load_owned_order",
    "update_case_fields",
]


@dataclass(frozen=True)
class Rendered:
    """Channel-specific content of one outbound message."""

    text: str
    subject: str | None = None
    html: str | None = None


@dataclass(frozen=True)
class Attempt:
    channel: Channel
    ok: bool
    provider_message_id: str | None
    error: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": str(self.channel),
            "ok": self.ok,
            "provider_message_id": self.provider_message_id,
            "error": self.error,
        }


def load_case(ctx: ToolContext) -> Case:
    case = ctx.repos.cases.get(ctx.case_id)
    if case is None:
        raise ToolError("case_not_found", "kasus untuk sesi ini tidak ditemukan")
    return case


def load_customer(ctx: ToolContext, case: Case) -> Customer:
    customer = ctx.repos.customers.get(case.customer_id)
    if customer is None:
        raise ToolError(
            "customer_not_found", "data pelanggan kasus ini tidak ditemukan"
        )
    return customer


def load_owned_order(ctx: ToolContext, case: Case, order_id: str) -> Order:
    """Return the order only if it belongs to the case's customer (else ``not_found``)."""
    normalized = order_id.strip().upper()
    order = ctx.repos.orders.get(normalized) if normalized else None
    if order is None or not owns_order(case, order):
        raise ToolError(
            "not_found", f"pesanan {normalized or '(kosong)'} tidak ditemukan"
        )
    return order


def update_case_fields(ctx: ToolContext, **updates: Any) -> Case:
    """Re-read the case, apply ``updates`` and write it back (avoids clobbering)."""
    case = load_case(ctx)
    updated = case.model_copy(update={**updates, "updated_at": ctx.now_iso()})
    ctx.repos.cases.put(updated)
    return updated


def fallback_chain(start: Channel, exclude: Sequence[Channel] = ()) -> list[Channel]:
    """``start`` followed by the channels after it in WhatsApp -> SMS -> email order."""
    order = list(DEFAULT_FALLBACK_ORDER)
    chain = [start] + order[order.index(start) + 1 :]
    return [c for c in chain if c == start or c not in exclude]


def consume_outbound(ctx: ToolContext) -> bool:
    """Reserve one outbound message from the per-turn budget."""
    if ctx.outbound >= policy.MAX_OUTBOUND_PER_TURN:
        return False
    ctx.outbound += 1
    return True


def _recipient(customer: Customer, channel: Channel) -> dict[str, str] | None:
    if channel is Channel.EMAIL:
        return {"to_email": customer.email} if customer.email else None
    return {"to_e164": customer.phone_e164}


def deliver(
    ctx: ToolContext,
    case: Case,
    customer: Customer,
    chain: Sequence[Channel],
    render: Callable[[Channel], Rendered],
) -> list[Attempt]:
    """Send one logical message along ``chain`` until a channel succeeds.

    Each attempt is stored in ``messages``. On the first successful outbound of the
    case, ``first_response_at`` is set.
    """
    attempts: list[Attempt] = []
    for channel in chain:
        recipient = _recipient(customer, channel)
        if recipient is None:
            continue
        content = render(channel)
        result = ctx.sender(
            channel,
            text=content.text,
            subject=content.subject,
            html=content.html,
            **recipient,
        )
        ts = ctx.now_iso()
        ctx.repos.messages.put(
            Message(
                case_id=case.case_id,
                msg_id=f"MSG-{uuid.uuid4().hex[:12]}",
                ts=ts,
                direction=MessageDirection.OUTBOUND,
                author=MessageAuthor.AGENT,
                channel=channel,
                body=content.text,
                provider_message_id=result.provider_message_id,
                delivery_status=DeliveryStatus.SENT
                if result.ok
                else DeliveryStatus.FAILED,
                error=result.error,
                created_at=ts,
            )
        )
        attempts.append(
            Attempt(channel, result.ok, result.provider_message_id, result.error)
        )
        if result.ok:
            if load_case(ctx).first_response_at is None:
                update_case_fields(ctx, first_response_at=ts)
            break
    return attempts


def _escalation_text(customer: Customer, on_duty: bool) -> str:
    hours = f"{policy.STAFF_HOURS_START:02d}.00-{policy.STAFF_HOURS_END:02d}.00 WIB"
    if customer.language is Language.EN:
        when = "shortly" if on_duty else f"during the next business hours ({hours})"
        return (
            "Thank you for your patience. Your case has been forwarded to our team, "
            f"and a staff member will contact you {when}."
        )
    when = "segera" if on_duty else f"pada jam kerja berikutnya ({hours})"
    return (
        "Terima kasih atas kesabaran Anda. Kasus Anda sudah kami teruskan ke tim kami "
        f"dan staf akan menghubungi Anda {when}."
    )


def escalate_case(
    ctx: ToolContext, reason: str, priority: CasePriority, *, notify: bool
) -> dict[str, Any]:
    """Mark the case escalated, log an ``escalation`` event and optionally tell the customer."""
    case = load_case(ctx)
    if case.status is CaseStatus.RESOLVED:
        raise ToolError(
            "invalid_transition", "kasus sudah selesai, tidak bisa dieskalasi"
        )
    if case.status is not CaseStatus.ESCALATED or case.priority is not priority:
        case = update_case_fields(
            ctx,
            status=CaseStatus.ESCALATED,
            priority=priority,
            resolution_type=ResolutionType.ESCALATED,
        )
    record_event(
        ctx,
        AgentEventType.ESCALATION,
        input_text=to_json({"reason": reason, "priority": str(priority)}),
    )

    on_duty = staff_on_duty(ctx.now())
    notified = False
    if notify and consume_outbound(ctx):
        customer = load_customer(ctx, case)
        text = _escalation_text(customer, on_duty)
        attempts = deliver(
            ctx, case, customer, fallback_chain(case.channel), lambda _: Rendered(text)
        )
        notified = any(a.ok for a in attempts)
    return {
        "escalated": True,
        "priority": str(priority),
        "staff_on_duty": on_duty,
        "customer_notified": notified,
    }
