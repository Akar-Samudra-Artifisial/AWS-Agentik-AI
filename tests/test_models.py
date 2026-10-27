"""Tests for pydantic models and enums."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resolveai_common.models import (
    Approval,
    ApprovalStatus,
    Case,
    CaseCategory,
    CasePriority,
    CaseStatus,
    Channel,
    Customer,
    DeliveryStatus,
    Language,
    Message,
    MessageAuthor,
    MessageDirection,
    Order,
    OrderItem,
    OrderStatus,
    PreferredChannel,
    ProcessedEvent,
)

_NOW = "2026-10-27T00:00:00Z"


def test_enum_values() -> None:
    assert Channel.WHATSAPP.value == "whatsapp"
    assert Language.ID.value == "id"
    assert OrderStatus.OUT_FOR_DELIVERY.value == "out_for_delivery"
    assert CaseStatus.AWAITING_APPROVAL.value == "awaiting_approval"
    assert CaseCategory.LOST_PACKAGE.value == "lost_package"
    assert ApprovalStatus.PENDING.value == "pending"
    assert DeliveryStatus.READ.value == "read"


def test_customer_defaults() -> None:
    cust = Customer(
        customer_id="CUST-0001",
        name="Rani",
        phone_e164="+6281234567890",
        created_at=_NOW,
    )
    assert cust.language is Language.ID
    assert cust.preferred_channel is PreferredChannel.WHATSAPP
    assert cust.email is None


def test_order_with_items() -> None:
    order = Order(
        order_id="ORD-1001",
        customer_id="CUST-0001",
        status=OrderStatus.IN_TRANSIT,
        items=[OrderItem(name="Sepatu", qty=1, price_idr=349_000)],
        total_idr=349_000,
        created_at=_NOW,
    )
    assert order.total_idr == 349_000
    assert order.items[0].price_idr == 349_000
    # Derived fields are not part of the model.
    assert not hasattr(order, "days_late")


def test_case_defaults() -> None:
    case = Case(
        case_id="CASE-20261027-0001",
        customer_id="CUST-0001",
        channel=Channel.WHATSAPP,
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert case.status is CaseStatus.OPEN
    assert case.priority is CasePriority.NORMAL
    assert case.resolution is None
    assert case.seeded is False


def test_message_and_approval() -> None:
    msg = Message(
        case_id="CASE-20261027-0001",
        msg_id="m1",
        ts=_NOW,
        direction=MessageDirection.INBOUND,
        author=MessageAuthor.CUSTOMER,
        channel=Channel.WHATSAPP,
        body="Pesanan terlambat",
        created_at=_NOW,
    )
    assert msg.delivery_status is DeliveryStatus.QUEUED

    apr = Approval(
        approval_id="APR-0001",
        case_id="CASE-20261027-0001",
        order_id="ORD-1002",
        amount_idr=349_000,
        reason="Refund paket hilang",
        requested_at=_NOW,
    )
    assert apr.action == "refund"
    assert apr.status is ApprovalStatus.PENDING


def test_processed_event() -> None:
    evt = ProcessedEvent(event_id="evt-1", ttl=1_900_000_000)
    assert evt.ttl == 1_900_000_000


def test_invalid_enum_rejected() -> None:
    with pytest.raises(ValidationError):
        Customer(
            customer_id="CUST-0001",
            name="Rani",
            phone_e164="+6281234567890",
            language="fr",  # type: ignore[arg-type]
            created_at=_NOW,
        )


def test_negative_amount_rejected() -> None:
    with pytest.raises(ValidationError):
        OrderItem(name="X", qty=1, price_idr=-1)


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        ProcessedEvent(event_id="evt-1", ttl=1, unexpected="x")  # type: ignore[call-arg]
