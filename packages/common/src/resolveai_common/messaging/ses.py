"""Amazon SES v2 email adapter (MSG-002).

Uses the ``sesv2`` client's ``send_email`` with ``Content.Simple`` (Subject + Html/Text
body). The sender address comes from ``SES_FROM_EMAIL`` (SSM/env) and is never
hardcoded. Region is resolved by boto3 from the standard chain.

Operation confirmed against the installed boto3 (``sesv2.send_email``; input
``FromEmailAddress``, ``Destination.ToAddresses``, ``Content.Simple{Subject,Body{Html,
Text}}``; output ``MessageId``).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..models import Channel
from .types import SendResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_sesv2.client import SESV2Client

__all__ = ["send_email"]

_FROM_EMAIL_ENV = "SES_FROM_EMAIL"


def send_email(
    to: str,
    subject: str,
    html: str,
    text: str,
    *,
    client: SESV2Client | None = None,
    from_email: str | None = None,
) -> SendResult:
    """Send an HTML+text email via SES v2. Never raises; returns a ``SendResult``.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html: HTML body.
        text: Plain-text alternative body.
        client: Optional pre-built ``sesv2`` client (tests inject a stubbed one).
        from_email: Sender override; defaults to ``SES_FROM_EMAIL`` from the env.

    Returns:
        ``SendResult`` with ``provider_message_id`` set to the SES ``MessageId`` on
        success, or ``error`` populated on failure.
    """
    sender = from_email or os.environ.get(_FROM_EMAIL_ENV)
    if not sender:
        return SendResult(
            ok=False,
            channel=Channel.EMAIL,
            error=f"{_FROM_EMAIL_ENV} is not configured",
        )

    ses = client if client is not None else boto3.client("sesv2")
    try:
        resp: dict[str, Any] = ses.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": [to]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html, "Charset": "UTF-8"},
                        "Text": {"Data": text, "Charset": "UTF-8"},
                    },
                }
            },
        )
    except (ClientError, BotoCoreError) as exc:
        return SendResult(ok=False, channel=Channel.EMAIL, error=str(exc))

    return SendResult(
        ok=True,
        channel=Channel.EMAIL,
        provider_message_id=resp.get("MessageId"),
        raw=resp,
    )
