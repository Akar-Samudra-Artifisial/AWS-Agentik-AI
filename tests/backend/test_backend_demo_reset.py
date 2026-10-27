"""``POST /api/demo/reset`` (BE-014): env guard, auth, and what is deleted vs kept."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from api.app import create_app
from backend_helpers import API_KEY, seed_case
from fastapi.testclient import TestClient
from resolveai_common.models import AgentEvent, Approval, Message, OrderStatus
from resolveai_common.seed_data import SEEDED_CASE_COUNT, build_seed_data, seed
from services.config import parse_iso
from services.data import scan_all
from services.deps import Deps
from services.trigger import InlineTrigger

HEADERS = {"x-api-key": API_KEY}
LIVE_CASE = "CASE-20261027-0001"
URL = "/api/demo/reset"


@pytest.fixture
def client(deps: Deps) -> Iterator[TestClient]:
    app = create_app(deps=deps, trigger=InlineTrigger(lambda: deps))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_RESET_ENABLED", "true")


def _seed_demo(deps: Deps) -> None:
    seed(
        deps.repos,
        build_seed_data(datetime.now(UTC), "+6281234567890", "rani@example.com"),
    )


def _seed_live_case(deps: Deps) -> None:
    seed_case(deps, LIVE_CASE, order_id="ORD-1002", lock_until="2099-01-01T00:00:00Z")
    deps.repos.messages.put(
        Message.model_validate(
            {
                "case_id": LIVE_CASE,
                "msg_id": "MSG-1",
                "ts": "2026-10-27T00:00:05Z",
                "direction": "inbound",
                "author": "customer",
                "channel": "whatsapp",
                "body": "ORD-1002 belum sampai",
                "created_at": "2026-10-27T00:00:05Z",
            }
        )
    )
    deps.repos.agent_events.put(
        AgentEvent.model_validate(
            {
                "case_id": LIVE_CASE,
                "ts": "2026-10-27T00:00:06Z",
                "seq": 1,
                "type": "model_message",
            }
        )
    )
    deps.repos.approvals.put(
        Approval.model_validate(
            {
                "approval_id": "APR-0001",
                "case_id": LIVE_CASE,
                "order_id": "ORD-1002",
                "amount_idr": 349000,
                "reason": "paket hilang",
                "status": "pending",
                "requested_at": "2026-10-27T01:00:00Z",
            }
        )
    )
    # Simulate what a demo take does to the scenario order (agent refund).
    order = deps.repos.orders.get("ORD-1002")
    assert order is not None
    deps.repos.orders.put(order.model_copy(update={"status": OrderStatus.REFUNDED}))


def test_reset_requires_api_key(client: TestClient, enabled: None) -> None:
    resp = client.post(URL)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_reset_disabled_without_env(
    client: TestClient, deps: Deps, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEMO_RESET_ENABLED", raising=False)
    seed_case(deps, LIVE_CASE)

    resp = client.post(URL, headers=HEADERS)

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
    assert deps.repos.cases.get(LIVE_CASE) is not None


def test_reset_deletes_non_seed_and_keeps_seed(
    client: TestClient, deps: Deps, enabled: None
) -> None:
    _seed_demo(deps)
    _seed_live_case(deps)
    before_seed_case = deps.repos.cases.get("CASE-SEED-0001")
    untouched_order = deps.repos.orders.get("ORD-1004")

    resp = client.post(URL, headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == {
        "cases": 1,
        "messages": 1,
        "agent_events": 1,
        "approvals": 1,
    }
    assert body["reset_orders"] == ["ORD-1001", "ORD-1002", "ORD-1003"]

    assert deps.repos.cases.get(LIVE_CASE) is None
    assert deps.repos.messages.list_for_case(LIVE_CASE) == []
    assert deps.repos.agent_events.list_for_case(LIVE_CASE) == []
    assert deps.repos.approvals.get("APR-0001") is None

    cases = scan_all(deps.table("cases"))
    assert len(cases) == SEEDED_CASE_COUNT
    assert all(c["seeded"] is True for c in cases)
    assert deps.repos.cases.get("CASE-SEED-0001") == before_seed_case
    assert deps.repos.orders.get("ORD-1004") == untouched_order
    assert len(scan_all(deps.table("customers"))) == 5

    order = deps.repos.orders.get("ORD-1002")
    assert order is not None and order.status is OrderStatus.IN_TRANSIT
    assert order.last_scan_at is not None
    age_days = (
        datetime.now(UTC) - parse_iso(order.last_scan_at)
    ).total_seconds() / 86400
    assert round(age_days) == 6


def test_reset_is_idempotent(client: TestClient, deps: Deps, enabled: None) -> None:
    _seed_demo(deps)
    _seed_live_case(deps)
    client.post(URL, headers=HEADERS)

    resp = client.post(URL, headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json()["deleted"] == {
        "cases": 0,
        "messages": 0,
        "agent_events": 0,
        "approvals": 0,
    }
