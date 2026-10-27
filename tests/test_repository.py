"""Tests for the DynamoDB repository layer (BE-002) against moto.

Covers put/get/query per table and GSI, Decimal <-> int conversion, inbound dedupe via
``processed_events`` and the conditional case lock (BE-007).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from _dynamo_schema import TABLES, create_tables
from moto import mock_aws
from resolveai_common.models import (
    AgentEvent,
    AgentEventType,
    Approval,
    ApprovalStatus,
    Case,
    CaseStatus,
    Channel,
    Customer,
    Message,
    MessageAuthor,
    MessageDirection,
    Order,
    OrderItem,
    OrderStatus,
    ProcessedEvent,
)
from resolveai_common.repository import (
    AGENT_EVENTS_SORT_KEY,
    MESSAGES_SORT_KEY,
    CaseLockedError,
    CaseNotFoundError,
    DuplicateEventError,
    Repositories,
    from_dynamo,
    to_dynamo,
)

PREFIX = "test"
NOW = "2026-10-28T03:00:00Z"


@pytest.fixture
def repos(monkeypatch: pytest.MonkeyPatch) -> Iterator[Repositories]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(resource, PREFIX)
        yield Repositories(prefix=PREFIX, dynamodb=resource)


def _case(
    case_id: str, status: CaseStatus, updated_at: str, customer_id: str = "CUST-1"
) -> Case:
    return Case(
        case_id=case_id,
        customer_id=customer_id,
        channel=Channel.WHATSAPP,
        status=status,
        created_at=updated_at,
        updated_at=updated_at,
    )


def _order(order_id: str, created_at: str, customer_id: str = "CUST-1") -> Order:
    return Order(
        order_id=order_id,
        customer_id=customer_id,
        status=OrderStatus.IN_TRANSIT,
        items=[OrderItem(name="Sepatu", qty=1, price_idr=349_000)],
        total_idr=349_000,
        created_at=created_at,
    )


# --------------------------------------------------------------------------- #
# Conversion helpers
# --------------------------------------------------------------------------- #
def test_from_dynamo_converts_decimals_recursively() -> None:
    item = {
        "a": Decimal(349000),
        "b": [Decimal(1), {"c": Decimal("2.5")}],
        "d": "x",
    }
    assert from_dynamo(item) == {"a": 349_000, "b": [1, {"c": 2.5}], "d": "x"}
    assert isinstance(from_dynamo(Decimal(3)), int)


def test_to_dynamo_drops_none_and_rejects_float() -> None:
    assert to_dynamo({"a": 1, "b": None, "c": [{"d": None, "e": True}]}) == {
        "a": 1,
        "c": [{"e": True}],
    }
    with pytest.raises(TypeError):
        to_dynamo({"price": 1.5})


# --------------------------------------------------------------------------- #
# Per-table round trips and GSIs
# --------------------------------------------------------------------------- #
def test_customer_put_get_and_find_by_phone(repos: Repositories) -> None:
    customer = Customer(
        customer_id="CUST-1", name="Budi", phone_e164="+628120000001", created_at=NOW
    )
    repos.customers.put(customer)

    assert repos.customers.get("CUST-1") == customer
    assert repos.customers.find_by_phone("+628120000001") == customer
    assert repos.customers.find_by_phone("+628129999999") is None
    assert repos.customers.get("CUST-404") is None


def test_order_round_trip_returns_int_money(repos: Repositories) -> None:
    repos.orders.put(_order("ORD-1", "2026-10-20T00:00:00Z"))

    order = repos.orders.get("ORD-1")
    assert order is not None
    assert order.total_idr == 349_000 and type(order.total_idr) is int
    assert type(order.items[0].price_idr) is int
    assert order.eta is None  # None fields dropped on write, defaulted on read


def test_order_find_by_customer_newest_first(repos: Repositories) -> None:
    repos.orders.put(_order("ORD-1", "2026-10-20T00:00:00Z"))
    repos.orders.put(_order("ORD-2", "2026-10-25T00:00:00Z"))
    repos.orders.put(_order("ORD-3", "2026-10-22T00:00:00Z", customer_id="CUST-2"))

    ids = [o.order_id for o in repos.orders.find_by_customer("CUST-1")]
    assert ids == ["ORD-2", "ORD-1"]


def test_case_queries_by_customer_and_status(repos: Repositories) -> None:
    repos.cases.put(_case("CASE-1", CaseStatus.OPEN, "2026-10-28T01:00:00Z"))
    repos.cases.put(_case("CASE-2", CaseStatus.RESOLVED, "2026-10-28T02:00:00Z"))
    repos.cases.put(_case("CASE-3", CaseStatus.OPEN, "2026-10-28T03:00:00Z", "CUST-2"))

    assert repos.cases.get("CASE-1") == _case(
        "CASE-1", CaseStatus.OPEN, "2026-10-28T01:00:00Z"
    )
    assert [c.case_id for c in repos.cases.find_by_customer("CUST-1")] == [
        "CASE-2",
        "CASE-1",
    ]
    assert [c.case_id for c in repos.cases.find_by_status(CaseStatus.OPEN)] == [
        "CASE-3",
        "CASE-1",
    ]
    assert [c.case_id for c in repos.cases.find_by_status("resolved")] == ["CASE-2"]


def _message(msg_id: str, ts: str) -> Message:
    return Message(
        case_id="CASE-1",
        msg_id=msg_id,
        ts=ts,
        direction=MessageDirection.INBOUND,
        author=MessageAuthor.CUSTOMER,
        channel=Channel.WHATSAPP,
        body=f"pesan {msg_id}",
        created_at=ts,
    )


def test_messages_listed_chronologically(repos: Repositories) -> None:
    repos.messages.put(_message("M2", "2026-10-28T01:00:02Z"))
    repos.messages.put(_message("M1", "2026-10-28T01:00:01Z"))
    repos.messages.put(_message("M3", "2026-10-28T01:00:03Z"))

    assert [m.msg_id for m in repos.messages.list_for_case("CASE-1")] == [
        "M1",
        "M2",
        "M3",
    ]
    assert repos.messages.list_for_case("CASE-404") == []


def test_messages_limit_is_respected(repos: Repositories) -> None:
    for i in range(1, 4):
        repos.messages.put(_message(f"M{i}", f"2026-10-28T01:00:0{i}Z"))

    assert [m.msg_id for m in repos.messages.list_for_case("CASE-1", limit=2)] == [
        "M1",
        "M2",
    ]


def test_messages_newest_returns_latest_in_chronological_order(
    repos: Repositories,
) -> None:
    for i in range(1, 6):
        repos.messages.put(_message(f"M{i}", f"2026-10-28T01:00:0{i}Z"))

    assert [
        m.msg_id for m in repos.messages.list_for_case("CASE-1", limit=2, newest=True)
    ] == ["M4", "M5"]
    assert [m.msg_id for m in repos.messages.list_for_case("CASE-1", newest=True)] == [
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
    ]


def test_agent_events_round_trip(repos: Repositories) -> None:
    for seq in (1, 0):
        repos.agent_events.put(
            AgentEvent(
                case_id="CASE-1",
                ts=NOW,
                seq=seq,
                type=AgentEventType.TOOL_CALL,
                tool="get_order",
                latency_ms=12,
            )
        )

    events = repos.agent_events.list_for_case("CASE-1")
    assert [e.seq for e in events] == [0, 1]
    assert events[0].latency_ms == 12 and type(events[0].latency_ms) is int


def test_approvals_get_and_find_by_status(repos: Repositories) -> None:
    pending = Approval(
        approval_id="APR-1",
        case_id="CASE-1",
        order_id="ORD-1",
        amount_idr=349_000,
        reason="paket hilang",
        requested_at="2026-10-28T01:00:00Z",
    )
    approved = pending.model_copy(
        update={
            "approval_id": "APR-2",
            "status": ApprovalStatus.APPROVED,
            "requested_at": "2026-10-28T02:00:00Z",
        }
    )
    repos.approvals.put(pending)
    repos.approvals.put(approved)

    assert repos.approvals.get("APR-1") == pending
    assert [a.approval_id for a in repos.approvals.find_by_status("pending")] == [
        "APR-1"
    ]
    assert [
        a.approval_id for a in repos.approvals.find_by_status(ApprovalStatus.APPROVED)
    ] == ["APR-2"]


# --------------------------------------------------------------------------- #
# Idempotency and locking
# --------------------------------------------------------------------------- #
def test_processed_event_dedupe(repos: Repositories) -> None:
    event = ProcessedEvent(event_id="evt-1", ttl=1_900_000_000)

    assert repos.processed_events.exists("evt-1") is False
    repos.processed_events.mark_processed(event)
    assert repos.processed_events.exists("evt-1") is True
    with pytest.raises(DuplicateEventError):
        repos.processed_events.mark_processed(event)


def test_case_lock_conditional(repos: Repositories) -> None:
    repos.cases.put(_case("CASE-1", CaseStatus.OPEN, "2026-10-28T01:00:00Z"))

    repos.cases.acquire_lock("CASE-1", lock_until="2026-10-28T03:02:30Z", now=NOW)
    with pytest.raises(CaseLockedError):
        repos.cases.acquire_lock("CASE-1", lock_until="2026-10-28T03:03:00Z", now=NOW)

    # Expired lock can be taken over.
    repos.cases.acquire_lock(
        "CASE-1", lock_until="2026-10-28T03:06:00Z", now="2026-10-28T03:03:00Z"
    )

    repos.cases.release_lock("CASE-1", now="2026-10-28T03:04:00Z")
    case = repos.cases.get("CASE-1")
    assert case is not None and case.lock_until is None
    repos.cases.acquire_lock("CASE-1", lock_until="2026-10-28T03:07:00Z", now=NOW)


def test_case_lock_on_missing_case_does_not_create_item(repos: Repositories) -> None:
    with pytest.raises(CaseNotFoundError):
        repos.cases.acquire_lock("CASE-404", lock_until="2026-10-28T03:02:30Z", now=NOW)

    assert repos.cases.get("CASE-404") is None


def test_sort_key_names_match_deployed_infra() -> None:
    """Regression: repository + moto schema must use the SK names deployed by CDK."""
    data_stack = (
        Path(__file__).resolve().parents[1] / "infra" / "stacks" / "data_stack.py"
    ).read_text()
    infra_sort_keys = dict(
        re.findall(r'self\._table\(prefix, "(\w+)", "\w+", sort_key="([^"]+)"\)', data_stack)
    )
    assert infra_sort_keys == {
        "messages": MESSAGES_SORT_KEY,
        "agent_events": AGENT_EVENTS_SORT_KEY,
    }
    assert TABLES["messages"][1] == MESSAGES_SORT_KEY
    assert TABLES["agent_events"][1] == AGENT_EVENTS_SORT_KEY
