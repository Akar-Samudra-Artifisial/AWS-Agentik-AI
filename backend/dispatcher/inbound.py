"""Inbound normalization (BE-004, MSG-008).

``parse_whatsapp_sns_event`` turns one SNS message published by AWS End User Messaging
Social into ``NormalizedInbound`` items (``changes[].value.messages[]``) and
``NormalizedStatus`` items (``changes[].value.statuses[]``, BE-013). The SNS ``Message``
is JSON with ``whatsAppWebhookEntry`` holding the Meta webhook entry as a JSON string (or
an object). Status events carry the AWS ``messageId`` returned by ``SendWhatsAppMessage``
at the envelope top level, which is what outbound messages store as
``provider_message_id``. Shapes are verified against real events in
``tests/fixtures/whatsapp_*.json``. Other fields (``account_update``, ``security``) yield
nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from resolveai_common.logging import get_logger
from resolveai_common.models import Channel, DeliveryStatus
from resolveai_common.phone import normalize_phone
from services.config import to_iso

__all__ = [
    "NormalizedInbound",
    "NormalizedStatus",
    "ParsedWhatsAppEvent",
    "parse_whatsapp_sns_event",
    "parse_whatsapp_sns_message",
]

# Meta status -> stored delivery status. ``accepted`` precedes ``sent``; others are skipped.
_META_STATUS = {
    "accepted": DeliveryStatus.SENT,
    "sent": DeliveryStatus.SENT,
    "delivered": DeliveryStatus.DELIVERED,
    "read": DeliveryStatus.READ,
    "failed": DeliveryStatus.FAILED,
}

_log = get_logger(__name__)


class NormalizedInbound(BaseModel):
    """Channel-agnostic inbound message (``02-backend.md`` §4 step 3)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    channel: Channel
    from_e164: str
    text: str
    received_at: str = Field(description="ISO 8601 UTC timestamp.")
    provider_message_id: str | None = None
    simulated: bool = False


class NormalizedStatus(BaseModel):
    """Delivery status update for an outbound WhatsApp message (BE-013)."""

    model_config = ConfigDict(extra="forbid")

    provider_message_id: str | None = Field(
        default=None, description="AWS messageId from the SNS envelope."
    )
    wamid: str | None = None
    recipient_e164: str | None = None
    status: DeliveryStatus
    error: str | None = None


class ParsedWhatsAppEvent(BaseModel):
    """Everything extracted from one EUM Social SNS message."""

    inbound: list[NormalizedInbound] = Field(default_factory=list)
    statuses: list[NormalizedStatus] = Field(default_factory=list)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return value


def _received_at(raw_ts: Any) -> str:
    try:
        return to_iso(datetime.fromtimestamp(int(raw_ts), UTC))
    except (TypeError, ValueError):
        return to_iso(datetime.now(UTC))


def _status_error(raw: dict[str, Any]) -> str | None:
    """``"<code> <title>"`` of the first Meta error, e.g. ``131031 Business Account locked``."""
    errors = raw.get("errors") or []
    if not errors or not isinstance(errors[0], dict):
        return None
    first = errors[0]
    parts = [
        str(p)
        for p in (first.get("code"), first.get("title") or first.get("message"))
        if p
    ]
    return " ".join(parts) or None


def _parse_status(raw: Any, provider_message_id: str | None) -> NormalizedStatus | None:
    if not isinstance(raw, dict):
        return None
    status = _META_STATUS.get(str(raw.get("status", "")))
    if status is None:
        _log.info("whatsapp status value skipped", extra={"status": raw.get("status")})
        return None
    return NormalizedStatus(
        provider_message_id=provider_message_id,
        wamid=raw.get("id"),
        recipient_e164=normalize_phone(raw.get("recipient_id")),
        status=status,
        error=_status_error(raw) if status is DeliveryStatus.FAILED else None,
    )


def parse_whatsapp_sns_event(sns_message: str | dict[str, Any]) -> ParsedWhatsAppEvent:
    """Extract customer text messages and delivery statuses from one EUM Social SNS
    message.

    Non-text messages, unknown status values, invalid sender numbers and non-message
    fields (``account_update``, ``security``) are logged and skipped.
    """
    _log.info("whatsapp raw event", extra={"raw_event": sns_message})
    try:
        envelope = _as_dict(sns_message)
        entry = _as_dict(envelope.get("whatsAppWebhookEntry", {}))
    except (TypeError, ValueError) as exc:
        _log.error("whatsapp event is not parseable", extra={"error": str(exc)})
        return ParsedWhatsAppEvent()

    envelope_message_id = envelope.get("messageId")
    parsed = ParsedWhatsAppEvent()
    results = parsed.inbound
    for change in entry.get("changes", []) or []:
        value = change.get("value", {}) if isinstance(change, dict) else {}
        for raw_status in value.get("statuses", []) or []:
            status = _parse_status(
                raw_status,
                str(envelope_message_id) if envelope_message_id else None,
            )
            if status is not None:
                parsed.statuses.append(status)
        for msg in value.get("messages", []) or []:
            msg_id = msg.get("id")
            if msg.get("type") != "text" or not msg_id:
                _log.info(
                    "whatsapp non-text message skipped", extra={"type": msg.get("type")}
                )
                continue
            from_e164 = normalize_phone(msg.get("from"))
            if from_e164 is None:
                _log.warning(
                    "whatsapp sender number invalid",
                    extra={"provider_message_id": msg_id},
                )
                continue
            results.append(
                NormalizedInbound(
                    event_id=f"wa#{msg_id}",
                    channel=Channel.WHATSAPP,
                    from_e164=from_e164,
                    text=str((msg.get("text") or {}).get("body", "")),
                    received_at=_received_at(msg.get("timestamp")),
                    provider_message_id=msg_id,
                )
            )
    return parsed


def parse_whatsapp_sns_message(
    sns_message: str | dict[str, Any],
) -> list[NormalizedInbound]:
    """Customer text messages only (see ``parse_whatsapp_sns_event``)."""
    return parse_whatsapp_sns_event(sns_message).inbound
