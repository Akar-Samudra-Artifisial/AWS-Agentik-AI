"""AWS End User Messaging SMS adapter (MSG-004, fallback channel).

Uses the ``pinpoint-sms-voice-v2`` client's ``send_text_message`` with
``MessageType="TRANSACTIONAL"``. The origination identity (phone number / sender id)
comes from ``SMS_ORIGINATION_IDENTITY`` (SSM/env).

Operation confirmed against the installed boto3 (``pinpoint-sms-voice-v2.send_text_message``;
required input ``DestinationPhoneNumber``; optional ``OriginationIdentity``,
``MessageBody``, ``MessageType``; output ``MessageId``).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..models import Channel
from .types import SendResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_pinpoint_sms_voice_v2.client import PinpointSMSVoiceV2Client

__all__ = ["send_sms"]

_ORIGINATION_IDENTITY_ENV = "SMS_ORIGINATION_IDENTITY"


def send_sms(
    to_e164: str,
    text: str,
    *,
    client: PinpointSMSVoiceV2Client | None = None,
    origination_identity: str | None = None,
) -> SendResult:
    """Send a transactional SMS. Never raises; returns a ``SendResult``.

    Args:
        to_e164: Recipient in E.164 (``+62…``).
        text: Message body.
        client: Optional pre-built ``pinpoint-sms-voice-v2`` client (tests inject a stub).
        origination_identity: Override; defaults to ``SMS_ORIGINATION_IDENTITY`` env.

    Returns:
        ``SendResult`` with ``provider_message_id`` set to ``MessageId`` on success.
    """
    identity = origination_identity or os.environ.get(_ORIGINATION_IDENTITY_ENV)
    if not identity:
        return SendResult(
            ok=False,
            channel=Channel.SMS,
            error=f"{_ORIGINATION_IDENTITY_ENV} is not configured",
        )

    sms = client if client is not None else boto3.client("pinpoint-sms-voice-v2")
    try:
        resp: dict[str, Any] = sms.send_text_message(
            DestinationPhoneNumber=to_e164,
            OriginationIdentity=identity,
            MessageBody=text,
            MessageType="TRANSACTIONAL",
        )
    except (ClientError, BotoCoreError) as exc:
        return SendResult(ok=False, channel=Channel.SMS, error=str(exc))

    return SendResult(
        ok=True,
        channel=Channel.SMS,
        provider_message_id=resp.get("MessageId"),
        raw=resp,
    )
