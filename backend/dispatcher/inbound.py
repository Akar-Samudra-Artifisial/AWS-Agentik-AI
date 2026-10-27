"""Inbound normalization (BE-004, MSG-008).

``parse_whatsapp_sns_message`` turns one SNS message published by AWS End User Messaging
Social into ``NormalizedInbound`` items. It is written against the documented event
shape: the SNS ``Message`` is JSON with ``whatsAppWebhookEntry`` holding the Meta webhook
entry (``changes[].value.messages[]``), either as a JSON string or an object.

TODO(MSG-008): verify against a real fixture captured from the deployed SNS topic and
save it under ``tests/fixtures/``; the raw event is logged (phones masked) for that.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from resolveai_common.logging import get_logger
from resolveai_common.models import Channel
from resolveai_common.phone import normalize_phone
from services.config import to_iso

__all__ = ["NormalizedInbound", "parse_whatsapp_sns_message"]

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


def parse_whatsapp_sns_message(
    sns_message: str | dict[str, Any],
) -> list[NormalizedInbound]:
    """Extract customer text messages from one EUM Social SNS message.

    Status updates (``value.statuses``) and non-text messages are logged and skipped
    (delivery status handling is BE-013, P1). Invalid sender numbers are skipped.
    """
    _log.info("whatsapp raw event", extra={"raw_event": sns_message})
    try:
        envelope = _as_dict(sns_message)
        entry = _as_dict(envelope.get("whatsAppWebhookEntry", {}))
    except (TypeError, ValueError) as exc:
        _log.error("whatsapp event is not parseable", extra={"error": str(exc)})
        return []

    results: list[NormalizedInbound] = []
    for change in entry.get("changes", []) or []:
        value = change.get("value", {}) if isinstance(change, dict) else {}
        if value.get("statuses"):
            _log.info(
                "whatsapp status event skipped", extra={"count": len(value["statuses"])}
            )
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
    return results
