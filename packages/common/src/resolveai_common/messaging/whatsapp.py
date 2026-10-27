"""AWS End User Messaging Social WhatsApp adapter (MSG-003).

Uses the ``socialmessaging`` client's ``send_whatsapp_message``. The Meta message
payload is serialized to a JSON ``bytes`` blob:
``{"messaging_product":"whatsapp","to":"<E.164>","type":"text","text":{"body":"…"}}``.
The origination phone number id comes from ``WA_PHONE_NUMBER_ID`` (SSM/env).

Operation confirmed against the installed boto3 (``socialmessaging.send_whatsapp_message``;
required input ``originationPhoneNumberId``, ``message`` (blob), ``metaApiVersion``;
output ``messageId``).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..models import Channel
from .types import SendResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_socialmessaging.client import EndUserMessagingSocialClient

__all__ = ["send_whatsapp", "build_whatsapp_payload"]

_PHONE_NUMBER_ID_ENV = "WA_PHONE_NUMBER_ID"
_META_API_VERSION_ENV = "WA_META_API_VERSION"
_DEFAULT_META_API_VERSION = "v20.0"


def build_whatsapp_payload(to_e164: str, text: str) -> bytes:
    """Build the Meta WhatsApp text-message payload as a JSON ``bytes`` blob."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to_e164,
        "type": "text",
        "text": {"body": text},
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def send_whatsapp(
    to_e164: str,
    text: str,
    *,
    client: EndUserMessagingSocialClient | None = None,
    origination_phone_number_id: str | None = None,
    meta_api_version: str | None = None,
) -> SendResult:
    """Send a WhatsApp text message. Never raises; returns a ``SendResult``.

    Args:
        to_e164: Recipient in E.164 (``+62…``).
        text: Message body.
        client: Optional pre-built ``socialmessaging`` client (tests inject a stub).
        origination_phone_number_id: Override; defaults to ``WA_PHONE_NUMBER_ID`` env.
        meta_api_version: Override; defaults to ``WA_META_API_VERSION`` env or ``v20.0``.

    Returns:
        ``SendResult`` with ``provider_message_id`` set to ``messageId`` on success.
    """
    phone_number_id = origination_phone_number_id or os.environ.get(_PHONE_NUMBER_ID_ENV)
    if not phone_number_id:
        return SendResult(
            ok=False,
            channel=Channel.WHATSAPP,
            error=f"{_PHONE_NUMBER_ID_ENV} is not configured",
        )

    api_version = (
        meta_api_version or os.environ.get(_META_API_VERSION_ENV) or _DEFAULT_META_API_VERSION
    )

    social = client if client is not None else boto3.client("socialmessaging")
    try:
        resp: dict[str, Any] = social.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=build_whatsapp_payload(to_e164, text),
            metaApiVersion=api_version,
        )
    except (ClientError, BotoCoreError) as exc:
        return SendResult(ok=False, channel=Channel.WHATSAPP, error=str(exc))

    return SendResult(
        ok=True,
        channel=Channel.WHATSAPP,
        provider_message_id=resp.get("messageId"),
        raw=resp,
    )
