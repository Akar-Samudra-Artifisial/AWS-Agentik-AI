"""Channel selection and fallback chain (MSG-005).

``send_on_channel`` routes a single send to the right adapter. ``send_with_fallback``
implements the WhatsApp -> SMS -> email chain from ``05-messaging.md`` §4: it tries each
channel in order until one succeeds, collecting every attempt's ``SendResult``.

Low-level adapters accept an explicit recipient; the recipient-ownership guard lives in
the agent layer, not here (per task scope).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..models import Channel
from .ses import send_email
from .sms import send_sms
from .types import SendResult
from .whatsapp import send_whatsapp

__all__ = ["DEFAULT_FALLBACK_ORDER", "send_on_channel", "send_with_fallback"]

# WhatsApp preferred, SMS fallback, email last resort.
DEFAULT_FALLBACK_ORDER: tuple[Channel, ...] = (Channel.WHATSAPP, Channel.SMS, Channel.EMAIL)


def send_on_channel(
    channel: Channel,
    *,
    text: str,
    to_e164: str | None = None,
    to_email: str | None = None,
    subject: str | None = None,
    html: str | None = None,
) -> SendResult:
    """Send ``text`` on a single channel, selecting the matching adapter.

    Args:
        channel: Target channel.
        text: Message/plain-text body (also used as the email text alternative).
        to_e164: Recipient phone for WhatsApp/SMS.
        to_email: Recipient email for the email channel.
        subject: Email subject (defaults to a generic ResolveAI subject).
        html: Email HTML body (defaults to ``text`` wrapped in a paragraph).

    Returns:
        A ``SendResult``; ``ok=False`` (without calling AWS) when the required
        recipient for the channel is missing.
    """
    if channel is Channel.WHATSAPP:
        if not to_e164:
            return SendResult(ok=False, channel=channel, error="missing to_e164 for whatsapp")
        return send_whatsapp(to_e164, text)

    if channel is Channel.SMS:
        if not to_e164:
            return SendResult(ok=False, channel=channel, error="missing to_e164 for sms")
        return send_sms(to_e164, text)

    if channel is Channel.EMAIL:
        if not to_email:
            return SendResult(ok=False, channel=channel, error="missing to_email for email")
        return send_email(
            to_email,
            subject or "[ResolveAI] Notifikasi",
            html or f"<p>{text}</p>",
            text,
        )

    return SendResult(ok=False, channel=channel, error=f"unsupported channel {channel!r}")


def send_with_fallback(
    *,
    text: str,
    to_e164: str | None = None,
    to_email: str | None = None,
    subject: str | None = None,
    html: str | None = None,
    order: Sequence[Channel] = DEFAULT_FALLBACK_ORDER,
) -> list[SendResult]:
    """Try channels in ``order`` until one succeeds (MSG-005).

    Channels whose required recipient is missing are skipped (not recorded as an
    attempt). Stops after the first success.

    Returns:
        The list of attempted ``SendResult``s, in attempt order. The last entry is the
        successful send when any channel succeeded; otherwise it holds every failure.
    """
    attempts: list[SendResult] = []
    for channel in order:
        if channel in (Channel.WHATSAPP, Channel.SMS) and not to_e164:
            continue
        if channel is Channel.EMAIL and not to_email:
            continue

        result = send_on_channel(
            channel,
            text=text,
            to_e164=to_e164,
            to_email=to_email,
            subject=subject,
            html=html,
        )
        attempts.append(result)
        if result.ok:
            break

    return attempts
