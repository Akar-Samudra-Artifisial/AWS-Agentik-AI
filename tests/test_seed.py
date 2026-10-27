"""Tests for scripts/seed.py (TST-001): idempotency, demo scenarios and env validation.

The script lives under ``scripts/`` (not a package), so it is loaded from its file path.
DynamoDB is mocked with moto; nothing is sent anywhere.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from _dynamo_schema import create_tables
from moto import mock_aws
from resolveai_common.models import CaseStatus, OrderStatus, ResolutionType
from resolveai_common.repository import Repositories

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed.py"
_PREFIX = "resolveai-test"
_PHONE = "+6281200000001"
_EMAIL = "demo@example.com"
_NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_cli", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


@pytest.fixture
def repos(monkeypatch: pytest.MonkeyPatch) -> Iterator[Repositories]:
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(resource, _PREFIX)
        yield Repositories(prefix=_PREFIX, dynamodb=resource)


def _count(repos: Repositories, attr: str) -> int:
    table = getattr(repos, attr)._table
    return table.scan(Select="COUNT")["Count"]


def _days(later: str, earlier: datetime) -> float:
    return (datetime.fromisoformat(later) - earlier).total_seconds() / 86400


def test_seed_is_idempotent(repos: Repositories) -> None:
    cli.seed(repos, cli.build_seed_data(_NOW, _PHONE, _EMAIL))
    first = {t: _count(repos, t) for t in ("customers", "orders", "cases")}
    cli.seed(repos, cli.build_seed_data(_NOW + timedelta(days=1), _PHONE, _EMAIL))
    second = {t: _count(repos, t) for t in ("customers", "orders", "cases")}

    assert (
        first == second == {"customers": 5, "orders": 8, "cases": cli.SEEDED_CASE_COUNT}
    )


def test_demo_customer_uses_env_contact(repos: Repositories) -> None:
    cli.seed(repos, cli.build_seed_data(_NOW, _PHONE, _EMAIL))

    rani = repos.customers.find_by_phone(_PHONE)
    assert rani is not None
    assert rani.customer_id == "CUST-0001"
    assert rani.name == "Rani"
    assert rani.email == _EMAIL
    others = [repos.customers.get(f"CUST-000{i}") for i in range(2, 6)]
    assert all(c is not None and c.phone_e164 != _PHONE for c in others)


def test_scenario_orders(repos: Repositories) -> None:
    cli.seed(repos, cli.build_seed_data(_NOW, _PHONE, _EMAIL))
    orders = {o.order_id: o for o in repos.orders.find_by_customer("CUST-0001")}

    assert sorted(orders) == [f"ORD-100{i}" for i in range(1, 9)]
    assert all(o.courier == "NusaExpress" for o in orders.values() if o.shipped_at)

    a, b, c = orders["ORD-1001"], orders["ORD-1002"], orders["ORD-1003"]
    assert (a.status, a.total_idr) == (OrderStatus.IN_TRANSIT, 189_000)
    assert a.eta is not None and round(_days(a.eta, _NOW)) == -2
    assert (b.status, b.total_idr) == (OrderStatus.IN_TRANSIT, 349_000)
    assert b.last_scan_at is not None and round(_days(b.last_scan_at, _NOW)) == -6
    assert (c.status, c.total_idr) == (OrderStatus.DELIVERED, 259_000)
    assert c.last_scan_at is not None and round(_days(c.last_scan_at, _NOW)) == -2
    assert orders["ORD-1006"].total_idr == 85_000
    assert orders["ORD-1007"].status is OrderStatus.PROCESSING


def test_seeded_cases_history(repos: Repositories) -> None:
    cli.seed(repos, cli.build_seed_data(_NOW, _PHONE, _EMAIL))
    cases = repos.cases.find_by_status(CaseStatus.RESOLVED)

    assert len(cases) == cli.SEEDED_CASE_COUNT
    assert all(c.seeded for c in cases)
    assert all(c.customer_id != "CUST-0001" for c in cases)
    auto = sum(c.resolution_type is ResolutionType.AUTO_RESOLVED for c in cases)
    assert 0.6 <= auto / len(cases) <= 0.8
    for case in cases:
        assert case.first_inbound_at and case.first_response_at and case.resolved_at
        age = -_days(case.first_inbound_at, _NOW)
        assert 0 < age <= 7
        response_s = (
            datetime.fromisoformat(case.first_response_at)
            - datetime.fromisoformat(case.first_inbound_at)
        ).total_seconds()
        assert 3 <= response_s <= 19


@pytest.mark.parametrize(
    ("env", "needle"),
    [
        ({}, "DEMO_PHONE_E164, DEMO_EMAIL"),
        ({"DEMO_PHONE_E164": _PHONE}, "DEMO_EMAIL"),
        ({"DEMO_PHONE_E164": "abc", "DEMO_EMAIL": _EMAIL}, "bukan nomor"),
        ({"DEMO_PHONE_E164": _PHONE, "DEMO_EMAIL": "nope"}, "bukan alamat email"),
    ],
)
def test_load_demo_contact_rejects_missing_or_invalid(
    env: dict[str, str], needle: str
) -> None:
    with pytest.raises(cli.SeedConfigError, match=needle):
        cli.load_demo_contact(env)


def test_main_exits_2_without_demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_PHONE_E164", raising=False)
    monkeypatch.delenv("DEMO_EMAIL", raising=False)

    assert cli.main([]) == 2
