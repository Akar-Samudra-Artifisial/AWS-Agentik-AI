"""Offline tests for the 11 agent tools and their code-level guards (``03-agent.md`` §6)."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

import boto3
import pytest
from _agent_support import CUSTOMER_EMAIL, CUSTOMER_PHONE, NOW, FakeSender, iso
from botocore.stub import Stubber
from resolveai_common import policy
from resolveai_common.messaging import ses
from resolveai_common.models import (
    AgentEventType,
    Approval,
    ApprovalStatus,
    CaseStatus,
    Channel,
    DeliveryStatus,
    MessageDirection,
    OrderStatus,
    ResolutionType,
)

from agent.context import ToolContext
from agent.tools import TOOL_NAMES, build_tools

Tools = dict[str, Callable[..., dict[str, Any]]]


def _error_code(result: dict[str, Any]) -> str | None:
    return None if result["ok"] else result["error"]["code"]


# --------------------------------------------------------------------------- #
# Surface: names, no recipient parameter
# --------------------------------------------------------------------------- #
_FORBIDDEN_PARAMS = {
    "to",
    "to_e164",
    "to_email",
    "recipient",
    "phone",
    "phone_e164",
    "email",
    "address",
    "destination",
    "customer_id",
    "case_id",
    "ctx",
}


def test_exactly_eleven_tools(tools: Tools) -> None:
    assert len(TOOL_NAMES) == 11
    assert set(tools) == set(TOOL_NAMES)


def test_no_tool_accepts_a_recipient(tools: Tools) -> None:
    for name, fn in tools.items():
        params = set(inspect.signature(fn).parameters)
        assert not params & _FORBIDDEN_PARAMS, (
            f"{name} exposes {params & _FORBIDDEN_PARAMS}"
        )
        assert fn.__doc__ and len(fn.__doc__) > 80, (
            f"{name} needs a descriptive docstring"
        )


def test_unknown_or_wrongly_typed_argument_is_rejected(tools: Tools) -> None:
    assert (
        _error_code(tools["send_message"](body="hai", to_e164="+628999"))
        == "invalid_input"
    )
    assert _error_code(tools["create_voucher"](amount_idr="25000")) == "invalid_input"


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
def test_get_order_derives_values_and_links_case(
    tools: Tools, ctx: ToolContext
) -> None:
    result = tools["get_order"](order_id="ord-late")

    assert result["ok"] is True
    assert result["days_late"] == 2
    assert result["eligibility"]["voucher"] is True
    assert "customer_id" not in result["order"]
    assert ctx.repos.cases.get("CASE-1").order_id == "ORD-LATE"


def test_get_order_of_another_customer_is_not_found(tools: Tools) -> None:
    assert _error_code(tools["get_order"](order_id="ORD-OTHER")) == "not_found"


def test_find_orders_by_customer_only_own_orders(tools: Tools) -> None:
    ids = {o["order_id"] for o in tools["find_orders_by_customer"]()["orders"]}
    assert ids == {"ORD-LATE", "ORD-LATE1", "ORD-LOST", "ORD-DELIV"}


# --------------------------------------------------------------------------- #
# Voucher
# --------------------------------------------------------------------------- #
def test_voucher_requires_linked_order(tools: Tools) -> None:
    assert _error_code(tools["create_voucher"](amount_idr=10_000)) == "order_required"


def test_voucher_cap_and_one_per_case(tools: Tools, ctx: ToolContext) -> None:
    tools["get_order"](order_id="ORD-LATE")

    over = tools["create_voucher"](amount_idr=policy.VOUCHER_MAX_IDR + 1)
    assert _error_code(over) == "amount_out_of_range"

    first = tools["create_voucher"](amount_idr=policy.VOUCHER_MAX_IDR)
    assert first["ok"] is True and first["voucher_code"].startswith("RAI-")
    assert (
        ctx.repos.cases.get("CASE-1").resolution.voucher_code == first["voucher_code"]
    )

    assert (
        _error_code(tools["create_voucher"](amount_idr=5_000))
        == "voucher_already_issued"
    )


def test_voucher_conditional_update_blocks_race(tools: Tools, ctx: ToolContext) -> None:
    tools["get_order"](order_id="ORD-LATE")
    real_load = ctx.repos.cases.get
    stale = real_load("CASE-1")
    assert tools["create_voucher"](amount_idr=10_000)["ok"]

    # Simulate a stale read that does not yet see the first voucher.
    ctx.repos.cases.get = lambda _cid: stale  # type: ignore[method-assign]
    assert (
        _error_code(tools["create_voucher"](amount_idr=10_000))
        == "voucher_already_issued"
    )


def test_voucher_not_eligible_when_only_one_day_late(tools: Tools) -> None:
    tools["get_order"](order_id="ORD-LATE1")
    assert _error_code(tools["create_voucher"](amount_idr=10_000)) == "not_eligible"


# --------------------------------------------------------------------------- #
# Redelivery
# --------------------------------------------------------------------------- #
def test_schedule_redelivery_default_tomorrow(tools: Tools, ctx: ToolContext) -> None:
    result = tools["schedule_redelivery"](order_id="ORD-LATE")

    assert result == {
        "ok": True,
        "order_id": "ORD-LATE",
        "redelivery_at": "2026-10-29T02:00:00Z",
        "simulated": True,
    }
    assert ctx.repos.orders.get("ORD-LATE").redelivery_at == "2026-10-29T02:00:00Z"
    assert ctx.repos.cases.get("CASE-1").resolution.action == "redelivery"


def test_schedule_redelivery_guards(tools: Tools) -> None:
    assert (
        _error_code(tools["schedule_redelivery"](order_id="ORD-DELIV"))
        == "not_eligible"
    )
    past = tools["schedule_redelivery"](
        order_id="ORD-LATE", preferred_date="2026-10-27"
    )
    assert _error_code(past) == "invalid_input"


# --------------------------------------------------------------------------- #
# Refund request / execution
# --------------------------------------------------------------------------- #
def _with_total(ctx: ToolContext, order_id: str, total: int) -> None:
    order = ctx.repos.orders.get(order_id)
    ctx.repos.orders.put(order.model_copy(update={"total_idr": total}))


@pytest.mark.parametrize(
    ("amount", "expected_status", "approval_status"),
    [
        (100_000, "auto_approved", ApprovalStatus.APPROVED),
        (100_001, "pending_approval", ApprovalStatus.PENDING),
    ],
)
def test_request_refund_auto_limit_boundary(
    tools: Tools,
    ctx: ToolContext,
    amount: int,
    expected_status: str,
    approval_status: ApprovalStatus,
) -> None:
    result = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=amount, reason="paket hilang"
    )

    assert result["ok"] is True and result["status"] == expected_status
    approval = ctx.repos.approvals.get(result["approval_id"])
    assert approval.status is approval_status
    assert approval.case_id == "CASE-1" and approval.amount_idr == amount
    if approval_status is ApprovalStatus.APPROVED:
        assert approval.decided_by == "policy"


def test_request_refund_guards(tools: Tools) -> None:
    req = tools["request_refund"]
    assert (
        _error_code(req(order_id="ORD-OTHER", amount_idr=1_000, reason="x"))
        == "not_found"
    )
    assert (
        _error_code(req(order_id="ORD-LATE", amount_idr=1_000, reason="x"))
        == "not_eligible"
    )
    over_total = req(order_id="ORD-LOST", amount_idr=349_001, reason="x")
    assert _error_code(over_total) == "amount_out_of_range"


def test_request_refund_is_idempotent(tools: Tools) -> None:
    first = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=349_000, reason="hilang"
    )
    second = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=349_000, reason="hilang"
    )

    assert second["approval_id"] == first["approval_id"]
    assert second["duplicate"] is True


def test_execute_refund_without_approval(tools: Tools) -> None:
    result = tools["execute_refund"](
        approval_id="APR-NOPE", order_id="ORD-LOST", amount_idr=1
    )
    assert _error_code(result) == "approval_required"


def _decide(ctx: ToolContext, approval_id: str, status: ApprovalStatus) -> None:
    approval = ctx.repos.approvals.get(approval_id)
    ctx.repos.approvals.put(
        approval.model_copy(
            update={"status": status, "decided_by": "staff", "decided_at": "t"}
        )
    )


def test_execute_refund_pending_and_rejected_are_refused(
    tools: Tools, ctx: ToolContext
) -> None:
    approval_id = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=349_000, reason="hilang"
    )["approval_id"]
    execute = tools["execute_refund"]

    pending = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=349_000)
    assert _error_code(pending) == "approval_required"

    _decide(ctx, approval_id, ApprovalStatus.REJECTED)
    rejected = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=349_000)
    assert _error_code(rejected) == "approval_required"
    assert ctx.repos.orders.get("ORD-LOST").status is OrderStatus.IN_TRANSIT


def test_execute_refund_amount_or_order_mismatch(
    tools: Tools, ctx: ToolContext
) -> None:
    approval_id = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=349_000, reason="hilang"
    )["approval_id"]
    _decide(ctx, approval_id, ApprovalStatus.APPROVED)
    execute = tools["execute_refund"]

    more = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=349_001)
    assert _error_code(more) == "approval_required"
    less = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=100_000)
    assert _error_code(less) == "approval_required"
    other = execute(approval_id=approval_id, order_id="ORD-LATE", amount_idr=349_000)
    assert _error_code(other) == "approval_required"


def test_execute_refund_approval_of_other_case(tools: Tools, ctx: ToolContext) -> None:
    ctx.repos.approvals.put(
        Approval(
            approval_id="APR-FOREIGN",
            case_id="CASE-OTHER",
            order_id="ORD-LOST",
            amount_idr=349_000,
            reason="x",
            status=ApprovalStatus.APPROVED,
            requested_at=iso(NOW),
        )
    )
    result = tools["execute_refund"](
        approval_id="APR-FOREIGN", order_id="ORD-LOST", amount_idr=349_000
    )
    assert _error_code(result) == "approval_required"


def test_execute_refund_once(tools: Tools, ctx: ToolContext) -> None:
    approval_id = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=349_000, reason="hilang"
    )["approval_id"]
    _decide(ctx, approval_id, ApprovalStatus.APPROVED)
    execute = tools["execute_refund"]

    first = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=349_000)
    assert first == {
        "ok": True,
        "status": "executed",
        "amount_idr": 349_000,
        "simulated": True,
    }
    order = ctx.repos.orders.get("ORD-LOST")
    assert order.status is OrderStatus.REFUNDED and order.refund.amount_idr == 349_000
    assert ctx.repos.cases.get("CASE-1").resolution.action == "refund"

    second = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=349_000)
    assert _error_code(second) == "already_executed"


def test_execute_refund_conditional_update_blocks_race(
    tools: Tools, ctx: ToolContext
) -> None:
    approval_id = tools["request_refund"](
        order_id="ORD-LOST", amount_idr=85_000, reason="hilang"
    )["approval_id"]
    stale_order = ctx.repos.orders.get("ORD-LOST")
    execute = tools["execute_refund"]
    assert execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=85_000)[
        "ok"
    ]

    # A concurrent turn that read the order before the first execution.
    ctx.repos.orders.get = lambda _oid: stale_order  # type: ignore[method-assign]
    second = execute(approval_id=approval_id, order_id="ORD-LOST", amount_idr=85_000)
    assert _error_code(second) == "already_executed"


# --------------------------------------------------------------------------- #
# Messaging
# --------------------------------------------------------------------------- #
def test_send_message_uses_case_customer_and_records(
    tools: Tools, ctx: ToolContext, sender: FakeSender
) -> None:
    result = tools["send_message"](body="Halo, pesanan Anda sedang kami cek.")

    assert result["ok"] is True and result["channel"] == "whatsapp"
    assert sender.calls == [
        {
            "channel": Channel.WHATSAPP,
            "text": "Halo, pesanan Anda sedang kami cek.",
            "subject": None,
            "html": None,
            "to_e164": CUSTOMER_PHONE,
        }
    ]
    [message] = ctx.repos.messages.list_for_case("CASE-1")
    assert message.direction is MessageDirection.OUTBOUND
    assert message.delivery_status is DeliveryStatus.SENT
    assert message.provider_message_id == result["provider_message_id"]
    assert ctx.repos.cases.get("CASE-1").first_response_at == message.ts


def test_send_message_falls_back_and_logs_each_attempt(
    tools: Tools, ctx: ToolContext, sender: FakeSender
) -> None:
    sender.failing.add(Channel.WHATSAPP)
    result = tools["send_message"](body="Halo")

    assert result["channel"] == "sms"
    statuses = [
        (m.channel, m.delivery_status)
        for m in ctx.repos.messages.list_for_case("CASE-1")
    ]
    assert sorted(statuses) == [
        (Channel.SMS, DeliveryStatus.SENT),
        (Channel.WHATSAPP, DeliveryStatus.FAILED),
    ]


def test_send_message_rejects_internal_ids_and_long_body(tools: Tools) -> None:
    assert (
        _error_code(tools["send_message"](body="ID Anda CUST-1"))
        == "internal_id_in_message"
    )
    assert _error_code(tools["send_message"](body="x" * 1001)) == "invalid_input"


def test_outbound_limit_per_turn(
    tools: Tools, ctx: ToolContext, sender: FakeSender
) -> None:
    for i in range(policy.MAX_OUTBOUND_PER_TURN):
        assert tools["send_message"](body=f"pesan {i}")["ok"] is True

    blocked = tools["send_message"](body="satu lagi")
    assert _error_code(blocked) == "outbound_limit_exceeded"
    assert len(sender.calls) == policy.MAX_OUTBOUND_PER_TURN
    assert ctx.repos.cases.get("CASE-1").status is CaseStatus.ESCALATED


def test_send_message_through_real_dispatch_with_ses_stubber(
    dynamodb: Any, ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default sender -> dispatch.send_on_channel -> SES adapter, with a stubbed client."""
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@example.com")
    client = boto3.client("sesv2", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "send_email",
        {"MessageId": "ses-123"},
        {
            "FromEmailAddress": "noreply@example.com",
            "Destination": {"ToAddresses": [CUSTOMER_EMAIL]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "[ResolveAI] Notifikasi", "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": "<p>Halo via email</p>", "Charset": "UTF-8"},
                        "Text": {"Data": "Halo via email", "Charset": "UTF-8"},
                    },
                }
            },
        },
    )
    real_client = boto3.client
    monkeypatch.setattr(
        ses.boto3,
        "client",
        lambda name, *a, **kw: (
            client if name == "sesv2" else real_client(name, *a, **kw)
        ),
    )
    real_ctx = ToolContext.create(
        "CASE-1", dynamodb=dynamodb, prefix="test", clock=lambda: NOW
    )
    send = {fn.__name__: fn for fn in build_tools(real_ctx)}["send_message"]

    with stubber:
        result = send(body="Halo via email", channel="email")

    stubber.assert_no_pending_responses()
    assert result["ok"] is True and result["provider_message_id"] == "ses-123"


def test_send_resolution_notice_inbound_plus_email(
    tools: Tools, ctx: ToolContext, sender: FakeSender
) -> None:
    tools["get_order"](order_id="ORD-LATE")
    voucher = tools["create_voucher"](amount_idr=25_000)["voucher_code"]

    result = tools["send_resolution_notice"](
        summary="Kami memberikan voucher kompensasi.",
        next_steps="Gunakan saat belanja.",
    )

    assert result == {
        "ok": True,
        "sent": [{"channel": "whatsapp", "ok": True}, {"channel": "email", "ok": True}],
    }
    wa, email = sender.calls
    assert (
        wa["to_e164"] == CUSTOMER_PHONE
        and voucher in wa["text"]
        and "CASE-1" in wa["text"]
    )
    assert email["to_email"] == CUSTOMER_EMAIL
    assert email["subject"] == "[ResolveAI] Kasus CASE-1 telah diselesaikan"


# --------------------------------------------------------------------------- #
# Case state, escalation, budgets, logging
# --------------------------------------------------------------------------- #
def test_update_case_transitions(tools: Tools, ctx: ToolContext) -> None:
    result = tools["update_case"](status="resolved", category="late_delivery")
    assert result["ok"] is True
    case = ctx.repos.cases.get("CASE-1")
    assert case.resolution_type is ResolutionType.AUTO_RESOLVED and case.resolved_at

    reopen = tools["update_case"](status="investigating")
    assert _error_code(reopen) == "invalid_transition"
    assert _error_code(tools["update_case"](status="escalated")) == "invalid_input"


def test_escalate_to_human_notifies_customer(
    tools: Tools, ctx: ToolContext, sender: FakeSender
) -> None:
    result = tools["escalate_to_human"](reason="ancaman lapor polisi", priority="high")

    assert result["ok"] is True and result["customer_notified"] is True
    case = ctx.repos.cases.get("CASE-1")
    assert (
        case.status is CaseStatus.ESCALATED
        and case.resolution_type is ResolutionType.ESCALATED
    )
    assert sender.calls[0]["to_e164"] == CUSTOMER_PHONE
    types = [e.type for e in ctx.repos.agent_events.list_for_case("CASE-1")]
    assert AgentEventType.ESCALATION in types


def test_tool_call_limit_escalates(tools: Tools, ctx: ToolContext) -> None:
    for _ in range(policy.MAX_TOOL_CALLS_PER_TURN):
        assert tools["find_orders_by_customer"]()["ok"] is True

    assert _error_code(tools["find_orders_by_customer"]()) == "tool_limit_exceeded"
    assert ctx.repos.cases.get("CASE-1").status is CaseStatus.ESCALATED


def test_logged_tool_records_call_and_truncated_result(
    tools: Tools, ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools["get_order"](order_id="ORD-LATE")
    tools["search_policy"](query="x" * 400 + " refund")

    events = ctx.repos.agent_events.list_for_case("CASE-1")
    get_call, get_result = events[0], events[1]
    assert (get_call.type, get_call.tool) == (AgentEventType.TOOL_CALL, "get_order")
    assert json.loads(get_call.input) == {"order_id": "ORD-LATE"}
    assert get_result.type is AgentEventType.TOOL_RESULT and get_result.ok is True
    assert get_result.latency_ms is not None
    assert all(len((e.output or "").encode()) <= 4096 for e in events)


def test_logged_tool_truncates_output_to_4kb(tools: Tools, ctx: ToolContext) -> None:
    tools["search_policy"](
        query="refund persetujuan staf hilang voucher eskalasi kurir"
    )
    result_event = ctx.repos.agent_events.list_for_case("CASE-1")[-1]
    assert result_event.output is not None
    assert len(result_event.output.encode("utf-8")) <= 4096


def test_unexpected_exception_becomes_internal_error(
    tools: Tools, ctx: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_order_id: str) -> None:
        raise RuntimeError("dynamo down")

    monkeypatch.setattr(ctx.repos.orders, "get", boom)
    assert _error_code(tools["get_order"](order_id="ORD-LATE")) == "internal_error"
    assert ctx.repos.agent_events.list_for_case("CASE-1")[-1].ok is False
