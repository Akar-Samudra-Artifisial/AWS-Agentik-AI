"""Seed builders shared by backend tests (synthetic data only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Case, Channel, Customer
from services.config import to_iso
from services.deps import Deps

API_KEY = "test-api-key"
DEMO_PHONE = "+6281234567890"


def iso_ago(**delta: float) -> str:
    return to_iso(datetime.now(UTC) - timedelta(**delta))


def seed_customer(
    deps: Deps, phone: str = DEMO_PHONE, email: str | None = "rani@example.com"
) -> Customer:
    customer = Customer(
        customer_id="CUST-0001",
        name="Rani",
        phone_e164=phone,
        email=email,
        created_at=iso_ago(days=30),
    )
    deps.repos.customers.put(customer)
    return customer


def seed_case(
    deps: Deps, case_id: str, customer_id: str = "CUST-0001", **fields: object
) -> Case:
    data: dict[str, object] = {
        "case_id": case_id,
        "customer_id": customer_id,
        "channel": "whatsapp",
        "created_at": iso_ago(days=2),
        "updated_at": iso_ago(hours=1),
    }
    data.update(fields)
    case = Case.model_validate(data)
    deps.repos.cases.put(case)
    return case


class StubInvoker:
    """Records invocations; returns ``response`` or raises ``error``."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str]] = []
        self.response: dict[str, Any] = {
            "case_status": "awaiting_customer",
            "actions": [],
        }
        self.error: Exception | None = None

    def invoke(self, payload: dict[str, Any], session_id: str) -> dict[str, Any]:
        self.calls.append((payload, session_id))
        if self.error is not None:
            raise self.error
        return {"case_id": payload["case_id"], **self.response}


class StubSender:
    """Records fail-safe sends; succeeds on the first channel of ``order``."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> list[SendResult]:
        self.calls.append(kwargs)
        channel: Channel = kwargs["order"][0]
        return [SendResult(ok=True, channel=channel, provider_message_id="stub-msg-1")]
