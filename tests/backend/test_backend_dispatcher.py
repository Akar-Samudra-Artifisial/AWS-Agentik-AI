"""Dispatcher core: SNS parsing, dedupe, case reuse, lock and fail-safe (BE-004..009)."""

from __future__ import annotations

import io
import json
import logging
from typing import Any

from backend_helpers import (
    DEMO_PHONE,
    StubInvoker,
    StubSender,
    iso_ago,
    seed_case,
    seed_customer,
)
from dispatcher.core import FAILSAFE_TEXT, handle_event, process_inbound, run_agent_turn
from dispatcher.inbound import NormalizedInbound, parse_whatsapp_sns_message
from resolveai_common.logging import JsonFormatter
from resolveai_common.models import CaseStatus, MessageAuthor, MessageDirection
from services.agent_client import SESSION_ID_MIN_LEN, session_id_for_case
from services.deps import Deps


def _wa_sns_message(
    msg_id: str = "wamid.TEST1", text: str = "Pesanan ORD-1001 terlambat"
) -> str:
    """Documented EUM Social shape: ``whatsAppWebhookEntry`` is a JSON string."""
    entry = {
        "id": "WABA-ID",
        "changes": [
            {
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [
                        {"profile": {"name": "Rani"}, "wa_id": DEMO_PHONE[1:]}
                    ],
                    "messages": [
                        {
                            "from": DEMO_PHONE[1:],
                            "id": msg_id,
                            "timestamp": "1793145600",
                            "type": "text",
                            "text": {"body": text},
                        }
                    ],
                },
            }
        ],
    }
    return json.dumps({"context": {}, "whatsAppWebhookEntry": json.dumps(entry)})


def _sns_event(message: str) -> dict[str, Any]:
    return {"Records": [{"EventSource": "aws:sns", "Sns": {"Message": message}}]}


def _inbound(event_id: str, text: str = "Halo") -> NormalizedInbound:
    return NormalizedInbound(
        event_id=event_id,
        channel="whatsapp",
        from_e164=DEMO_PHONE,
        text=text,
        received_at=iso_ago(seconds=1),
        simulated=True,
    )


def test_parser_extracts_text_message() -> None:
    [inbound] = parse_whatsapp_sns_message(_wa_sns_message())
    assert inbound.event_id == "wa#wamid.TEST1"
    assert inbound.from_e164 == DEMO_PHONE
    assert inbound.text == "Pesanan ORD-1001 terlambat"
    assert inbound.received_at.endswith("Z")


def test_parser_skips_status_and_garbage() -> None:
    status_entry = {
        "changes": [{"value": {"statuses": [{"id": "wamid.X", "status": "read"}]}}]
    }
    assert (
        parse_whatsapp_sns_message(json.dumps({"whatsAppWebhookEntry": status_entry}))
        == []
    )
    assert parse_whatsapp_sns_message("not json") == []


def test_sns_duplicate_processed_once(deps: Deps, invoker: StubInvoker) -> None:
    event = _sns_event(_wa_sns_message())
    first = handle_event(deps, event)
    second = handle_event(deps, event)

    assert first["processed"] == 1
    assert second == {"processed": 0, "skipped": 1, "turns": []}
    assert len(invoker.calls) == 1
    case_id = first["turns"][0]["case_id"]
    assert len(deps.repos.messages.list_for_case(case_id)) == 1


def test_logs_never_contain_full_phone(deps: Deps) -> None:
    stream = io.StringIO()
    log_handler = logging.StreamHandler(stream)
    log_handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(log_handler)
    previous_level = root.level
    root.setLevel(logging.INFO)
    try:
        handle_event(deps, _sns_event(_wa_sns_message(msg_id="wamid.LOG")))
    finally:
        root.removeHandler(log_handler)
        root.setLevel(previous_level)

    output = stream.getvalue()
    assert "whatsapp raw event" in output
    assert DEMO_PHONE[3:] not in output


def test_unknown_number_creates_customer_and_case(
    deps: Deps, invoker: StubInvoker
) -> None:
    result = process_inbound(deps, _inbound("evt-1"))
    assert result is not None and result.status == "ok"

    customer = deps.repos.customers.find_by_phone(DEMO_PHONE)
    assert customer is not None and customer.name == "Pelanggan baru"
    case = deps.repos.cases.get(result.case_id)
    assert case is not None
    assert case.case_id.startswith("CASE-") and len(case.case_id) == len(
        "CASE-20261028-0001"
    )
    assert case.first_inbound_at is not None
    assert case.lock_until is None  # released after the turn

    payload, session_id = invoker.calls[0]
    assert payload["event_type"] == "customer_message"
    assert payload["message"]["text"] == "Halo"
    assert payload["customer"]["phone_e164"] == DEMO_PHONE
    assert len(session_id) >= SESSION_ID_MIN_LEN
    assert session_id == session_id_for_case(case.case_id)


def test_case_reused_within_window(deps: Deps, invoker: StubInvoker) -> None:
    seed_customer(deps)
    seed_case(
        deps,
        "CASE-20261027-0001",
        status="awaiting_customer",
        updated_at=iso_ago(hours=2),
    )
    seed_case(
        deps, "CASE-20261027-0002", status="resolved", updated_at=iso_ago(minutes=5)
    )

    result = process_inbound(deps, _inbound("evt-2", text="1"))
    assert result is not None and result.case_id == "CASE-20261027-0001"

    payload, _ = invoker.calls[0]
    assert payload["history"] == []  # the current message is passed as ``message``


def test_new_case_when_outside_window_or_closed(deps: Deps) -> None:
    seed_customer(deps)
    seed_case(deps, "CASE-20261020-0001", status="open", updated_at=iso_ago(hours=25))
    seed_case(
        deps, "CASE-20261027-0003", status="escalated", updated_at=iso_ago(minutes=5)
    )

    result = process_inbound(deps, _inbound("evt-3"))
    assert result is not None
    assert result.case_id not in {"CASE-20261020-0001", "CASE-20261027-0003"}


def test_locked_case_turn_is_skipped(deps: Deps, invoker: StubInvoker) -> None:
    seed_customer(deps)
    seed_case(deps, "CASE-20261027-0004", status="open")
    deps.repos.cases.acquire_lock(
        "CASE-20261027-0004", lock_until=iso_ago(seconds=-120), now=iso_ago(seconds=0)
    )

    result = run_agent_turn(deps, "CASE-20261027-0004", "customer_message")
    assert result.status == "locked"
    assert invoker.calls == []


def test_failsafe_escalates_and_apologizes_once(
    deps: Deps, invoker: StubInvoker, sender: StubSender
) -> None:
    seed_customer(deps)
    seed_case(deps, "CASE-20261027-0005", status="awaiting_customer")
    invoker.error = TimeoutError("read timeout")

    first = run_agent_turn(deps, "CASE-20261027-0005", "customer_message")
    second = run_agent_turn(deps, "CASE-20261027-0005", "customer_message")

    assert first.status == second.status == "failsafe"
    case = deps.repos.cases.get("CASE-20261027-0005")
    assert case is not None
    assert case.status is CaseStatus.ESCALATED
    assert case.priority.value == "high"
    assert case.first_response_at is not None
    assert case.lock_until is None

    assert len(sender.calls) == 1  # apology sent once per case
    assert sender.calls[0]["to_e164"] == DEMO_PHONE
    apologies = [
        m
        for m in deps.repos.messages.list_for_case("CASE-20261027-0005")
        if m.direction is MessageDirection.OUTBOUND and m.author is MessageAuthor.SYSTEM
    ]
    assert [m.body for m in apologies] == [FAILSAFE_TEXT]
    assert apologies[0].provider_message_id == "stub-msg-1"

    event_types = [
        e.type.value
        for e in deps.repos.agent_events.list_for_case("CASE-20261027-0005")
    ]
    assert "error" in event_types and "escalation" in event_types


def test_agent_error_response_triggers_failsafe(
    deps: Deps, invoker: StubInvoker
) -> None:
    seed_customer(deps)
    seed_case(deps, "CASE-20261027-0006", status="open")
    invoker.response = {"error": "model throttled"}

    result = run_agent_turn(deps, "CASE-20261027-0006", "customer_message")
    assert result.status == "failsafe"
    case = deps.repos.cases.get("CASE-20261027-0006")
    assert case is not None and case.status is CaseStatus.ESCALATED
