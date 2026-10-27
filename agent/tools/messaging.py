"""Customer messaging tools: ``send_message`` and ``send_resolution_notice``.

Neither tool takes a recipient: phone/email come from the case's customer record and
the channel defaults to the case's inbound channel. Sends go through the real AWS
messaging adapters (``ctx.sender``); tests inject fakes.
"""

from typing import Any, Literal

from resolveai_common import policy
from resolveai_common.messaging.templates import (
    render_email,
    render_sms,
    render_whatsapp,
)
from resolveai_common.models import Channel

from ..context import ToolContext
from ..guards import check_message_body
from .base import ToolError, ok
from .core import (
    Rendered,
    consume_outbound,
    deliver,
    fallback_chain,
    load_case,
    load_customer,
)
from .registry import auto_escalate, logged_tool

__all__ = ["send_message", "send_resolution_notice"]

MAX_NOTICE_FIELD_CHARS = 300
DEFAULT_NEXT_STEPS = "Tidak ada tindakan lain yang perlu Anda lakukan."

ChannelName = Literal["whatsapp", "sms", "email"]


def _reserve_outbound(ctx: ToolContext) -> None:
    if not consume_outbound(ctx):
        auto_escalate(ctx, "batas pesan keluar per giliran terlampaui", notify=False)
        raise ToolError(
            "outbound_limit_exceeded",
            f"batas {policy.MAX_OUTBOUND_PER_TURN} pesan keluar per giliran tercapai; "
            "akhiri giliran",
        )


@logged_tool
def send_message(
    ctx: ToolContext, body: str, channel: ChannelName | None = None
) -> dict[str, Any]:
    """Kirim pesan percakapan ke pelanggan kasus ini.

    Send a conversational message (answer, question, numbered options) to this case's
    customer. The recipient is always the case's customer; by default the message goes
    out on the channel the customer wrote in on, falling back WhatsApp -> SMS -> email
    if delivery fails. Plain text, max 1000 characters, no internal IDs. Do not use
    this for the final resolution notice (use send_resolution_notice).

    Args:
        body: Message text in the customer's language.
        channel: Optional channel override: "whatsapp", "sms" or "email".

    Returns:
        ``{ok, channel, provider_message_id, attempts}``; ``ok`` is false when every
        channel failed.
    """
    violation = check_message_body(body)
    if violation:
        raise ToolError.from_violation(violation)
    case = load_case(ctx)
    customer = load_customer(ctx, case)
    start = Channel(channel) if channel else case.channel
    if start is Channel.EMAIL and not customer.email:
        raise ToolError("no_email", "pelanggan tidak punya email; pakai kanal lain")
    _reserve_outbound(ctx)

    text = body.strip()
    attempts = deliver(
        ctx, case, customer, fallback_chain(start), lambda _: Rendered(text)
    )
    success = next((a for a in attempts if a.ok), None)
    if success is None:
        return {
            "ok": False,
            "error": {
                "code": "delivery_failed",
                "message": "semua kanal gagal mengirim",
            },
            "attempts": [a.as_dict() for a in attempts],
        }
    return ok(
        channel=str(success.channel),
        provider_message_id=success.provider_message_id,
        attempts=[a.as_dict() for a in attempts],
    )


@logged_tool
def send_resolution_notice(
    ctx: ToolContext, summary: str, next_steps: str | None = None
) -> dict[str, Any]:
    """Kirim notifikasi penyelesaian kasus (template tetap) ke pelanggan.

    Send the deterministic final resolution notice after the action is done: on the
    customer's inbound channel (with SMS fallback for WhatsApp) and, if the customer has
    an email, also by email. Any voucher code on the case is included automatically.
    Call update_case(status="resolved") afterwards.

    Args:
        summary: One or two sentences describing what was done (max 300 characters).
        next_steps: What happens next for the customer (max 300 characters).

    Returns:
        ``{ok, sent: [{channel, ok}]}``; ``ok`` is true if at least one channel delivered.
    """
    summary = summary.strip()
    steps = (next_steps or DEFAULT_NEXT_STEPS).strip()
    if not summary or len(summary) > MAX_NOTICE_FIELD_CHARS:
        raise ToolError(
            "invalid_input",
            f"summary wajib diisi, maks {MAX_NOTICE_FIELD_CHARS} karakter",
        )
    if len(steps) > MAX_NOTICE_FIELD_CHARS:
        raise ToolError(
            "invalid_input", f"next_steps maks {MAX_NOTICE_FIELD_CHARS} karakter"
        )
    for text in (summary, steps):
        violation = check_message_body(text)
        if violation:
            raise ToolError.from_violation(violation)

    case = load_case(ctx)
    customer = load_customer(ctx, case)
    params = {
        "case_id": case.case_id,
        "customer_name": customer.name,
        "summary": summary,
        "next_steps": steps,
        "voucher_code": case.resolution.voucher_code if case.resolution else None,
    }

    def render(channel: Channel) -> Rendered:
        if channel is Channel.WHATSAPP:
            return Rendered(render_whatsapp(**params))
        if channel is Channel.SMS:
            return Rendered(render_sms(**params))
        email = render_email(**params)
        return Rendered(email.text, subject=email.subject, html=email.html)

    with_email = customer.email is not None and case.channel is not Channel.EMAIL
    chains = [
        fallback_chain(case.channel, exclude=[Channel.EMAIL] if with_email else [])
    ]
    if with_email:
        chains.append([Channel.EMAIL])

    sent: list[dict[str, Any]] = []
    for chain in chains:
        _reserve_outbound(ctx)
        try:
            attempts = deliver(ctx, case, customer, chain, render)
        except ValueError as exc:  # template length guard
            raise ToolError("invalid_input", str(exc)) from exc
        sent.extend({"channel": str(a.channel), "ok": a.ok} for a in attempts)
    if not any(item["ok"] for item in sent):
        return {
            "ok": False,
            "error": {
                "code": "delivery_failed",
                "message": "notifikasi gagal di semua kanal",
            },
            "sent": sent,
        }
    return ok(sent=sent)
