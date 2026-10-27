"""Tests for the messaging adapters (MSG-002/003/004).

Adapters are exercised offline with ``botocore.stub.Stubber`` (PRD 05 §7). Each adapter
must never raise: botocore errors surface as ``SendResult(ok=False, error=...)`` and a
missing origination identity short-circuits before any AWS call.
"""

from __future__ import annotations

import json

import boto3
import pytest
from botocore.stub import Stubber
from resolveai_common.messaging.ses import send_email
from resolveai_common.messaging.sms import send_sms
from resolveai_common.messaging.whatsapp import build_whatsapp_payload, send_whatsapp
from resolveai_common.models import Channel

_REGION = "us-east-1"


# --------------------------------------------------------------------------- #
# SES (MSG-002)
# --------------------------------------------------------------------------- #
def test_send_email_success() -> None:
    client = boto3.client("sesv2", region_name=_REGION)
    stubber = Stubber(client)
    expected_params = {
        "FromEmailAddress": "from@example.com",
        "Destination": {"ToAddresses": ["to@example.com"]},
        "Content": {
            "Simple": {
                "Subject": {"Data": "Subjek", "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": "<p>halo</p>", "Charset": "UTF-8"},
                    "Text": {"Data": "halo", "Charset": "UTF-8"},
                },
            }
        },
    }
    stubber.add_response("send_email", {"MessageId": "ses-123"}, expected_params)

    with stubber:
        result = send_email(
            "to@example.com",
            "Subjek",
            "<p>halo</p>",
            "halo",
            client=client,
            from_email="from@example.com",
        )

    assert result.ok is True
    assert result.channel is Channel.EMAIL
    assert result.provider_message_id == "ses-123"
    assert result.error is None


def test_send_email_missing_from_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SES_FROM_EMAIL", raising=False)

    result = send_email("to@example.com", "s", "<p>h</p>", "h")

    assert result.ok is False
    assert result.channel is Channel.EMAIL
    assert result.provider_message_id is None
    assert "SES_FROM_EMAIL" in (result.error or "")


def test_send_email_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SES_FROM_EMAIL", "env-from@example.com")
    client = boto3.client("sesv2", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_response(
        "send_email",
        {"MessageId": "ses-env"},
        {
            "FromEmailAddress": "env-from@example.com",
            "Destination": {"ToAddresses": ["to@example.com"]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "s", "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": "<p>h</p>", "Charset": "UTF-8"},
                        "Text": {"Data": "h", "Charset": "UTF-8"},
                    },
                }
            },
        },
    )

    with stubber:
        result = send_email("to@example.com", "s", "<p>h</p>", "h", client=client)

    assert result.ok is True
    assert result.provider_message_id == "ses-env"


def test_send_email_client_error_is_caught() -> None:
    client = boto3.client("sesv2", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_client_error("send_email", service_error_code="MessageRejected")

    with stubber:
        result = send_email(
            "to@example.com",
            "s",
            "<p>h</p>",
            "h",
            client=client,
            from_email="from@example.com",
        )

    assert result.ok is False
    assert result.channel is Channel.EMAIL
    assert "MessageRejected" in (result.error or "")


# --------------------------------------------------------------------------- #
# SMS (MSG-004)
# --------------------------------------------------------------------------- #
def test_send_sms_success() -> None:
    client = boto3.client("pinpoint-sms-voice-v2", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_response(
        "send_text_message",
        {"MessageId": "sms-123"},
        {
            "DestinationPhoneNumber": "+6281234567890",
            "OriginationIdentity": "ORIG-ID",
            "MessageBody": "halo",
            "MessageType": "TRANSACTIONAL",
        },
    )

    with stubber:
        result = send_sms(
            "+6281234567890", "halo", client=client, origination_identity="ORIG-ID"
        )

    assert result.ok is True
    assert result.channel is Channel.SMS
    assert result.provider_message_id == "sms-123"


def test_send_sms_missing_identity_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMS_ORIGINATION_IDENTITY", raising=False)

    result = send_sms("+6281234567890", "halo")

    assert result.ok is False
    assert result.channel is Channel.SMS
    assert "SMS_ORIGINATION_IDENTITY" in (result.error or "")


def test_send_sms_client_error_is_caught() -> None:
    client = boto3.client("pinpoint-sms-voice-v2", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_client_error(
        "send_text_message", service_error_code="ThrottlingException"
    )

    with stubber:
        result = send_sms(
            "+6281234567890", "halo", client=client, origination_identity="ORIG-ID"
        )

    assert result.ok is False
    assert "ThrottlingException" in (result.error or "")


# --------------------------------------------------------------------------- #
# WhatsApp (MSG-003)
# --------------------------------------------------------------------------- #
def test_build_whatsapp_payload_shape() -> None:
    raw = build_whatsapp_payload("+6281234567890", "halo dunia")
    payload = json.loads(raw.decode("utf-8"))

    assert payload == {
        "messaging_product": "whatsapp",
        "to": "+6281234567890",
        "type": "text",
        "text": {"body": "halo dunia"},
    }


def test_build_whatsapp_payload_keeps_unicode() -> None:
    raw = build_whatsapp_payload("+628", "diselesaikan ✓")

    # ensure_ascii=False keeps the character as a single UTF-8 glyph, not an escape.
    assert "✓".encode() in raw


def test_send_whatsapp_success() -> None:
    client = boto3.client("socialmessaging", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_response(
        "send_whatsapp_message",
        {"messageId": "wa-123"},
        {
            "originationPhoneNumberId": "PN-1",
            "message": build_whatsapp_payload("+6281234567890", "halo"),
            "metaApiVersion": "v20.0",
        },
    )

    with stubber:
        result = send_whatsapp(
            "+6281234567890",
            "halo",
            client=client,
            origination_phone_number_id="PN-1",
        )

    assert result.ok is True
    assert result.channel is Channel.WHATSAPP
    assert result.provider_message_id == "wa-123"


def test_send_whatsapp_missing_phone_number_id_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WA_PHONE_NUMBER_ID", raising=False)

    result = send_whatsapp("+6281234567890", "halo")

    assert result.ok is False
    assert result.channel is Channel.WHATSAPP
    assert "WA_PHONE_NUMBER_ID" in (result.error or "")


def test_send_whatsapp_meta_api_version_override() -> None:
    client = boto3.client("socialmessaging", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_response(
        "send_whatsapp_message",
        {"messageId": "wa-v21"},
        {
            "originationPhoneNumberId": "PN-1",
            "message": build_whatsapp_payload("+628", "halo"),
            "metaApiVersion": "v21.0",
        },
    )

    with stubber:
        result = send_whatsapp(
            "+628",
            "halo",
            client=client,
            origination_phone_number_id="PN-1",
            meta_api_version="v21.0",
        )

    assert result.ok is True
    assert result.provider_message_id == "wa-v21"


def test_send_whatsapp_client_error_is_caught() -> None:
    client = boto3.client("socialmessaging", region_name=_REGION)
    stubber = Stubber(client)
    stubber.add_client_error(
        "send_whatsapp_message", service_error_code="AccessDeniedException"
    )

    with stubber:
        result = send_whatsapp(
            "+628", "halo", client=client, origination_phone_number_id="PN-1"
        )

    assert result.ok is False
    assert "AccessDeniedException" in (result.error or "")
