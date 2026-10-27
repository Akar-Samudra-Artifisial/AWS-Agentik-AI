"""API endpoints (BE-010..012): auth, cases, approvals, simulate inbound, metrics."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from api.app import create_app
from backend_helpers import API_KEY, DEMO_PHONE, StubInvoker, seed_case, seed_customer
from fastapi.testclient import TestClient
from resolveai_common.models import (
    Approval,
    Message,
)
from services.deps import Deps
from services.trigger import InlineTrigger

HEADERS = {"x-api-key": API_KEY}


@pytest.fixture
def client(deps: Deps) -> Iterator[TestClient]:
    app = create_app(deps=deps, trigger=InlineTrigger(lambda: deps))
    with TestClient(app) as test_client:
        yield test_client


def _seed_approval(
    deps: Deps, approval_id: str = "APR-0001", status: str = "pending"
) -> None:
    deps.repos.approvals.put(
        Approval.model_validate(
            {
                "approval_id": approval_id,
                "case_id": "CASE-20261027-0001",
                "order_id": "ORD-1002",
                "amount_idr": 349000,
                "reason": "paket hilang",
                "status": status,
                "requested_at": "2026-10-27T01:00:00Z",
            }
        )
    )


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("headers", [{}, {"x-api-key": "wrong"}])
def test_auth_rejects_missing_or_wrong_key(
    client: TestClient, headers: dict[str, str]
) -> None:
    resp = client.get("/api/cases", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "path", ["/api/health", "/api/cases", "/api/approvals/APR-0001/decision"]
)
def test_cors_preflight_is_204_without_api_key(client: TestClient, path: str) -> None:
    resp = client.options(
        path,
        headers={
            "Origin": "https://example.cloudfront.net",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    assert resp.status_code == 204
    assert resp.content == b""


def test_simulate_inbound_creates_case_and_message(
    client: TestClient, deps: Deps, invoker: StubInvoker
) -> None:
    resp = client.post(
        "/api/simulate/inbound",
        headers=HEADERS,
        json={
            "channel": "whatsapp",
            "from_e164": "081234567890",
            "text": "ORD-1001 terlambat",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    case_id = body["case_id"]
    assert body["event_id"] and case_id.startswith("CASE-")

    [message] = deps.repos.messages.list_for_case(case_id)
    assert message.body == "ORD-1001 terlambat" and message.simulated is True
    customer = deps.repos.customers.find_by_phone(DEMO_PHONE)
    assert customer is not None

    [(payload, _)] = invoker.calls
    assert payload["event_type"] == "customer_message"
    assert payload["case_id"] == case_id

    detail = client.get(f"/api/cases/{case_id}", headers=HEADERS)
    assert detail.status_code == 200
    assert detail.json()["customer"]["phone_e164"] == DEMO_PHONE
    assert len(detail.json()["messages"]) == 1


def test_simulate_inbound_validates_input(client: TestClient) -> None:
    bad_phone = client.post(
        "/api/simulate/inbound",
        headers=HEADERS,
        json={"channel": "whatsapp", "from_e164": "12", "text": "hi"},
    )
    assert bad_phone.status_code == 400
    assert bad_phone.json()["error"]["code"] == "validation_error"

    bad_channel = client.post(
        "/api/simulate/inbound",
        headers=HEADERS,
        json={"channel": "fax", "from_e164": DEMO_PHONE, "text": "hi"},
    )
    assert bad_channel.status_code == 400


def test_decision_202_then_409_and_agent_invoked_once(
    client: TestClient, deps: Deps, invoker: StubInvoker
) -> None:
    seed_customer(deps)
    seed_case(
        deps, "CASE-20261027-0001", status="awaiting_approval", order_id="ORD-1002"
    )
    _seed_approval(deps)

    pending = client.get("/api/approvals", headers=HEADERS).json()
    assert [a["approval_id"] for a in pending] == ["APR-0001"]
    assert pending[0]["case"]["customer_name"] == "Rani"

    body = {"decision": "approve", "decided_by": "dimas", "note": "ok"}
    first = client.post("/api/approvals/APR-0001/decision", headers=HEADERS, json=body)
    assert first.status_code == 202
    assert first.json() == {"approval_id": "APR-0001", "status": "approved"}

    second = client.post("/api/approvals/APR-0001/decision", headers=HEADERS, json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"

    assert len(invoker.calls) == 1
    payload, _ = invoker.calls[0]
    assert payload["event_type"] == "approval_decided"
    assert payload["approval"] == {
        "approval_id": "APR-0001",
        "status": "approved",
        "note": "ok",
    }

    approval = deps.repos.approvals.get("APR-0001")
    assert approval is not None and approval.decided_by == "dimas"
    assert client.get("/api/approvals", headers=HEADERS).json() == []


def test_decision_unknown_approval_404(client: TestClient) -> None:
    resp = client.post(
        "/api/approvals/APR-404/decision",
        headers=HEADERS,
        json={"decision": "reject", "decided_by": "dimas"},
    )
    assert resp.status_code == 404
    assert resp.json() == {
        "error": {"code": "not_found", "message": "approval APR-404 not found"}
    }


def test_cases_list_filters_and_case_404(client: TestClient, deps: Deps) -> None:
    seed_customer(deps)
    seed_case(
        deps, "CASE-20261027-0001", status="open", updated_at="2026-10-27T01:00:00Z"
    )
    seed_case(
        deps,
        "CASE-20261027-0002",
        status="resolved",
        channel="email",
        updated_at="2026-10-27T02:00:00Z",
    )

    all_cases = client.get("/api/cases", headers=HEADERS).json()
    assert [c["case_id"] for c in all_cases] == [
        "CASE-20261027-0002",
        "CASE-20261027-0001",
    ]
    assert all_cases[0]["customer_name"] == "Rani"

    by_status = client.get("/api/cases?status=open", headers=HEADERS).json()
    assert [c["case_id"] for c in by_status] == ["CASE-20261027-0001"]
    by_channel = client.get("/api/cases?channel=email&limit=1", headers=HEADERS).json()
    assert [c["case_id"] for c in by_channel] == ["CASE-20261027-0002"]

    missing = client.get("/api/cases/CASE-NOPE", headers=HEADERS)
    assert missing.status_code == 404


def _message(
    case_id: str, msg_id: str, direction: str, channel: str, status: str
) -> Message:
    return Message.model_validate(
        {
            "case_id": case_id,
            "msg_id": msg_id,
            "ts": "2026-10-27T00:00:05Z",
            "direction": direction,
            "author": "agent" if direction == "outbound" else "customer",
            "channel": channel,
            "body": "x",
            "delivery_status": status,
            "created_at": "2026-10-27T00:00:05Z",
        }
    )


def test_metrics_from_seed(client: TestClient, deps: Deps) -> None:
    t0 = "2026-10-27T00:00:00Z"
    seed_customer(deps)
    seed_case(
        deps,
        "CASE-A",
        status="resolved",
        resolution_type="auto_resolved",
        category="late_delivery",
        first_inbound_at=t0,
        first_response_at="2026-10-27T00:00:10Z",
        resolved_at="2026-10-27T00:10:00Z",
    )
    seed_case(
        deps,
        "CASE-B",
        status="resolved",
        resolution_type="approved_by_staff",
        channel="email",
        category="lost_package",
        first_inbound_at=t0,
        first_response_at="2026-10-27T00:00:20Z",
        resolved_at="2026-10-27T00:20:00Z",
    )
    seed_case(
        deps,
        "CASE-C",
        status="escalated",
        resolution_type="escalated",
        channel="sms",
        category="not_received",
        first_inbound_at=t0,
        first_response_at="2026-10-27T00:00:30Z",
    )
    seed_case(deps, "CASE-D", status="open")
    _seed_approval(deps, "APR-1", "pending")
    _seed_approval(deps, "APR-2", "approved")
    for message in (
        _message("CASE-A", "m1", "outbound", "whatsapp", "sent"),
        _message("CASE-A", "m2", "outbound", "whatsapp", "read"),
        _message("CASE-A", "m3", "inbound", "whatsapp", "delivered"),
        _message("CASE-B", "m4", "outbound", "email", "failed"),
        _message("CASE-C", "m5", "outbound", "sms", "delivered"),
    ):
        deps.repos.messages.put(message)

    metrics = client.get("/api/metrics", headers=HEADERS).json()
    assert metrics["totals"] == {
        "cases": 4,
        "active": 1,
        "resolved": 2,
        "escalated": 1,
        "pending_approvals": 1,
    }
    assert metrics["auto_resolution_rate"] == pytest.approx(0.3333)
    assert metrics["first_response_ms"] == {"p50": 20000, "p90": 30000}
    assert metrics["resolution_ms"] == {"p50": 600000}
    assert metrics["by_channel"] == {"whatsapp": 2, "sms": 1, "email": 1}
    assert metrics["by_category"]["late_delivery"] == 1
    assert metrics["by_category"]["other"] == 1
    assert metrics["messages_sent"] == {"whatsapp": 2, "sms": 1, "email": 0}


def test_openapi_contains_contract_paths(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/health",
        "/api/cases",
        "/api/cases/{case_id}",
        "/api/approvals",
        "/api/approvals/{approval_id}/decision",
        "/api/simulate/inbound",
        "/api/metrics",
    ):
        assert path in paths
