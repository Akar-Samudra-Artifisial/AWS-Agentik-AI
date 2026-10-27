"""Delivery status webhooks (BE-013) against sanitized real EUM Social events.

Fixtures in ``tests/fixtures/whatsapp_*.json`` were captured from the deployed SNS topic
(``whatsapp raw event`` log) with ids, phone numbers and the account id replaced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from backend_helpers import StubInvoker, iso_ago, seed_case, seed_customer
from dispatcher.core import handle_event, process_status
from dispatcher.inbound import NormalizedStatus, parse_whatsapp_sns_event
from resolveai_common.models import (
    Channel,
    DeliveryStatus,
    Message,
    MessageAuthor,
    MessageDirection,
)
from services.deps import Deps

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FIXTURE_PHONE = "+6281200000001"
AWS_MESSAGE_ID = "00000000-0000-4000-8000-000000000001"
CASE_ID = "CASE-20261027-0A01"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _with_status(status: str) -> str:
    """The real ``failed`` event rewritten to another status value."""
    envelope = json.loads(_fixture("whatsapp_status_failed.json"))
    entry = json.loads(envelope["whatsAppWebhookEntry"])
    raw = entry["changes"][0]["value"]["statuses"][0]
    raw["status"] = status
    raw.pop("errors", None)
    envelope["whatsAppWebhookEntry"] = json.dumps(entry)
    return json.dumps(envelope)


def _sns(*messages: str) -> dict[str, Any]:
    return {
        "Records": [{"EventSource": "aws:sns", "Sns": {"Message": m}} for m in messages]
    }


def _seed_outbound(
    deps: Deps,
    status: DeliveryStatus = DeliveryStatus.SENT,
    provider_message_id: str = AWS_MESSAGE_ID,
) -> Message:
    seed_customer(deps, phone=FIXTURE_PHONE)
    seed_case(deps, CASE_ID, status="awaiting_customer")
    message = Message(
        case_id=CASE_ID,
        msg_id="m-out-1",
        ts=iso_ago(minutes=1),
        direction=MessageDirection.OUTBOUND,
        author=MessageAuthor.AGENT,
        channel=Channel.WHATSAPP,
        body="Baik, kami cek pesanan Anda.",
        provider_message_id=provider_message_id,
        delivery_status=status,
        created_at=iso_ago(minutes=1),
    )
    deps.repos.messages.put(message)
    return message


def _stored(deps: Deps) -> Message:
    [message] = deps.repos.messages.list_for_case(CASE_ID)
    return message


def test_parser_reads_real_failed_status() -> None:
    parsed = parse_whatsapp_sns_event(_fixture("whatsapp_status_failed.json"))
    assert parsed.inbound == []
    assert parsed.statuses == [
        NormalizedStatus(
            provider_message_id=AWS_MESSAGE_ID,
            wamid="wamid.TESTOUT1",
            recipient_e164=FIXTURE_PHONE,
            status=DeliveryStatus.FAILED,
            error="131031 Business Account locked",
        )
    ]


def test_parser_maps_accepted_to_sent() -> None:
    [status] = parse_whatsapp_sns_event(
        _fixture("whatsapp_status_accepted.json")
    ).statuses
    assert status.status is DeliveryStatus.SENT
    assert status.error is None


def test_parser_reads_real_text_message() -> None:
    parsed = parse_whatsapp_sns_event(_fixture("whatsapp_text_message.json"))
    assert parsed.statuses == []
    [inbound] = parsed.inbound
    assert inbound.event_id == "wa#wamid.TESTINBOUND1"
    assert inbound.from_e164 == "+6281200000002"


@pytest.mark.parametrize(
    ("meta_status", "expected"),
    [
        ("delivered", DeliveryStatus.DELIVERED),
        ("read", DeliveryStatus.READ),
    ],
)
def test_status_updates_outbound_message(
    deps: Deps, meta_status: str, expected: DeliveryStatus
) -> None:
    _seed_outbound(deps)
    result = handle_event(deps, _sns(_with_status(meta_status)))
    assert result["statuses"] == ["updated"]
    assert _stored(deps).delivery_status is expected


def test_failed_status_stores_error(deps: Deps, invoker: StubInvoker) -> None:
    _seed_outbound(deps)
    result = handle_event(deps, _sns(_fixture("whatsapp_status_failed.json")))

    assert result == {
        "processed": 0,
        "skipped": 0,
        "turns": [],
        "statuses": ["updated"],
    }
    message = _stored(deps)
    assert message.delivery_status is DeliveryStatus.FAILED
    assert message.error == "131031 Business Account locked"
    assert invoker.calls == []


@pytest.mark.parametrize(
    ("current", "meta_status"),
    [
        (DeliveryStatus.READ, "delivered"),
        (DeliveryStatus.DELIVERED, "sent"),
        (DeliveryStatus.READ, "failed"),
        (DeliveryStatus.FAILED, "read"),
        (DeliveryStatus.SENT, "accepted"),
    ],
)
def test_status_never_moves_backwards(
    deps: Deps, current: DeliveryStatus, meta_status: str
) -> None:
    _seed_outbound(deps, status=current)
    result = handle_event(deps, _sns(_with_status(meta_status)))
    assert result["statuses"] == ["unchanged"]
    assert _stored(deps).delivery_status is current


def test_concurrent_change_is_not_overwritten(deps: Deps) -> None:
    stale = _seed_outbound(deps, status=DeliveryStatus.SENT)
    deps.repos.messages.update_delivery_status(stale, DeliveryStatus.READ)

    assert not deps.repos.messages.update_delivery_status(
        stale, DeliveryStatus.DELIVERED
    )
    assert _stored(deps).delivery_status is DeliveryStatus.READ


def test_unmatched_status_creates_nothing(deps: Deps, invoker: StubInvoker) -> None:
    # Customer exists but the message id belongs to no stored message (e.g. a test send).
    _seed_outbound(deps, provider_message_id="other-id")
    result = handle_event(deps, _sns(_fixture("whatsapp_status_failed.json")))

    assert result["statuses"] == ["unmatched"]
    assert _stored(deps).delivery_status is DeliveryStatus.SENT
    assert invoker.calls == []


def test_status_for_unknown_number_creates_no_customer_or_case(
    deps: Deps, invoker: StubInvoker
) -> None:
    status = parse_whatsapp_sns_event(_fixture("whatsapp_status_failed.json")).statuses[
        0
    ]
    assert process_status(deps, status) == "unmatched"
    assert deps.repos.customers.find_by_phone(FIXTURE_PHONE) is None
    assert invoker.calls == []


@pytest.mark.parametrize(
    "fixture",
    [
        "whatsapp_account_update.json",
        "whatsapp_security.json",
        "whatsapp_status_failed.json",
        "whatsapp_status_accepted.json",
    ],
)
def test_non_message_events_never_create_cases(
    deps: Deps, invoker: StubInvoker, fixture: str
) -> None:
    result = handle_event(deps, _sns(_fixture(fixture)))

    assert result["processed"] == 0 and result["turns"] == []
    assert deps.repos.customers.find_by_phone(FIXTURE_PHONE) is None
    assert deps.table("cases").scan()["Items"] == []
    assert invoker.calls == []
