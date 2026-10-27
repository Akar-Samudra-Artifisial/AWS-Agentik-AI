"""Fixtures for agent tool tests: moto DynamoDB, seeded synthetic data, fake sender.

``_agent_support`` (imported first) puts the repo root on ``sys.path`` so the
top-level ``agent`` package is importable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import boto3
import pytest
from _agent_support import CUSTOMER_EMAIL, CUSTOMER_PHONE, NOW, PREFIX, FakeSender, iso
from _dynamo_schema import create_tables
from moto import mock_aws
from resolveai_common.models import (
    Case,
    CaseStatus,
    Channel,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
)

from agent.context import ToolContext
from agent.tools import build_tools


def _order(
    order_id: str, customer_id: str, status: OrderStatus, total: int, **kw: Any
) -> Order:
    return Order(
        order_id=order_id,
        customer_id=customer_id,
        status=status,
        items=[OrderItem(name="Barang uji", qty=1, price_idr=total)],
        total_idr=total,
        courier="KurirSim",
        created_at=iso(NOW - timedelta(days=10)),
        **kw,
    )


@pytest.fixture
def dynamodb(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(resource, PREFIX)
        yield resource


@pytest.fixture
def sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def ctx(dynamodb: Any, sender: FakeSender) -> ToolContext:
    context = ToolContext.create(
        "CASE-1", dynamodb=dynamodb, prefix=PREFIX, sender=sender, clock=lambda: NOW
    )
    repos = context.repos
    repos.customers.put(
        Customer(
            customer_id="CUST-1",
            name="Budi",
            phone_e164=CUSTOMER_PHONE,
            email=CUSTOMER_EMAIL,
            created_at=iso(NOW - timedelta(days=30)),
        )
    )
    repos.customers.put(
        Customer(
            customer_id="CUST-2",
            name="Sari",
            phone_e164="+628000000002",
            created_at=iso(NOW - timedelta(days=30)),
        )
    )
    in_transit = OrderStatus.IN_TRANSIT
    repos.orders.put(
        _order(
            "ORD-LATE",
            "CUST-1",
            in_transit,
            150_000,
            eta=iso(NOW - timedelta(days=2)),
            last_scan_at=iso(NOW - timedelta(days=1)),
        )
    )
    repos.orders.put(
        _order(
            "ORD-LATE1",
            "CUST-1",
            in_transit,
            150_000,
            eta=iso(NOW - timedelta(days=1)),
            last_scan_at=iso(NOW - timedelta(hours=5)),
        )
    )
    repos.orders.put(
        _order(
            "ORD-LOST",
            "CUST-1",
            in_transit,
            349_000,
            last_scan_at=iso(NOW - timedelta(days=6)),
        )
    )
    repos.orders.put(
        _order(
            "ORD-DELIV", "CUST-1", OrderStatus.DELIVERED, 99_000, last_scan_at=iso(NOW)
        )
    )
    repos.orders.put(
        _order(
            "ORD-OTHER",
            "CUST-2",
            in_transit,
            349_000,
            last_scan_at=iso(NOW - timedelta(days=9)),
        )
    )
    repos.cases.put(
        Case(
            case_id="CASE-1",
            customer_id="CUST-1",
            channel=Channel.WHATSAPP,
            status=CaseStatus.INVESTIGATING,
            created_at=iso(NOW),
            updated_at=iso(NOW),
        )
    )
    return context


@pytest.fixture
def tools(ctx: ToolContext) -> dict[str, Callable[..., dict[str, Any]]]:
    return {fn.__name__: fn for fn in build_tools(ctx)}
