"""Demo data reset between recording takes (BE-014, ``POST /api/demo/reset``).

Deletes every non-seed case (``seeded`` not true) together with its messages, agent
events and approvals (the case lock lives on the case item, so it goes with it), and
rebuilds the scenario orders ORD-1001..1003 from ``resolveai_common.seed_data`` with dates
relative to now. Seeded cases, customers and the other orders are left untouched.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from resolveai_common.repository import AGENT_EVENTS_SORT_KEY, MESSAGES_SORT_KEY
from resolveai_common.seed_data import build_orders

from .data import scan_all
from .deps import Deps

__all__ = [
    "DEMO_RESET_ENV",
    "SCENARIO_ORDER_IDS",
    "DemoResetResult",
    "is_demo_reset_enabled",
    "reset_demo",
]

DEMO_RESET_ENV = "DEMO_RESET_ENABLED"
SCENARIO_ORDER_IDS = ("ORD-1001", "ORD-1002", "ORD-1003")


@dataclass
class DemoResetResult:
    deleted: dict[str, int] = field(default_factory=dict)
    reset_orders: list[str] = field(default_factory=list)


def is_demo_reset_enabled() -> bool:
    """True only when ``DEMO_RESET_ENABLED`` is explicitly ``true`` (default off)."""
    return os.environ.get(DEMO_RESET_ENV, "").strip().lower() == "true"


def _delete(table: Any, keys: list[dict[str, Any]]) -> int:
    with table.batch_writer() as batch:
        for key in keys:
            batch.delete_item(Key=key)
    return len(keys)


def reset_demo(deps: Deps, now: datetime) -> DemoResetResult:
    """Delete non-seed cases (+ related items) and restore the scenario orders."""
    cases = scan_all(deps.table("cases"))
    seeded_ids = {c["case_id"] for c in cases if c.get("seeded") is True}
    result = DemoResetResult()
    result.deleted["cases"] = _delete(
        deps.table("cases"),
        [{"case_id": c["case_id"]} for c in cases if c["case_id"] not in seeded_ids],
    )
    for name, sort_key in (
        ("messages", MESSAGES_SORT_KEY),
        ("agent_events", AGENT_EVENTS_SORT_KEY),
    ):
        table = deps.table(name)
        result.deleted[name] = _delete(
            table,
            [
                {"case_id": item["case_id"], sort_key: item[sort_key]}
                for item in scan_all(table)
                if item["case_id"] not in seeded_ids
            ],
        )
    approvals = deps.table("approvals")
    result.deleted["approvals"] = _delete(
        approvals,
        [
            {"approval_id": item["approval_id"]}
            for item in scan_all(approvals)
            if item.get("case_id") not in seeded_ids
        ],
    )
    for order in build_orders(now):
        if order.order_id in SCENARIO_ORDER_IDS:
            deps.repos.orders.put(order)
            result.reset_orders.append(order.order_id)
    return result
