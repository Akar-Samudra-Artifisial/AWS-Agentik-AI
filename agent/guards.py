"""Pure guard functions enforced in tool code (``03-agent.md`` §6).

Every check returns ``None`` when allowed or a ``Violation`` (code + message) the tool
turns into a structured ``{ok: false, error: {code, message}}`` result. Policy numbers
are read from ``resolveai_common.policy`` at call time (single source of truth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from resolveai_common import policy
from resolveai_common.models import (
    Approval,
    ApprovalStatus,
    Case,
    CaseStatus,
    Order,
    OrderStatus,
)

__all__ = [
    "MAX_MESSAGE_CHARS",
    "REDELIVERY_STATUSES",
    "OrderInsights",
    "Violation",
    "check_message_body",
    "check_redelivery",
    "check_refund_execution",
    "check_refund_request",
    "check_status_transition",
    "check_voucher",
    "order_insights",
    "owns_order",
    "parse_ts",
    "refund_needs_approval",
    "staff_on_duty",
]

MAX_MESSAGE_CHARS = 1000

# Orders still with the courier: eligible for redelivery and for the "lost" rule.
REDELIVERY_STATUSES = frozenset(
    {OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT, OrderStatus.OUT_FOR_DELIVERY}
)
_CLOSED_ORDER_STATUSES = frozenset(
    {OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REFUNDED}
)

# Internal identifiers that must never reach the customer (order and case codes may).
_INTERNAL_ID_RE = re.compile(r"\b(?:CUST|APR|MSG)-[A-Z0-9-]+", re.IGNORECASE)

_ALLOWED_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.OPEN: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.AWAITING_CUSTOMER,
            CaseStatus.AWAITING_APPROVAL,
            CaseStatus.ESCALATED,
            CaseStatus.RESOLVED,
            CaseStatus.ERROR,
        }
    ),
    CaseStatus.INVESTIGATING: frozenset(
        {
            CaseStatus.AWAITING_CUSTOMER,
            CaseStatus.AWAITING_APPROVAL,
            CaseStatus.ESCALATED,
            CaseStatus.RESOLVED,
            CaseStatus.ERROR,
        }
    ),
    CaseStatus.AWAITING_CUSTOMER: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.AWAITING_APPROVAL,
            CaseStatus.ESCALATED,
            CaseStatus.RESOLVED,
            CaseStatus.ERROR,
        }
    ),
    CaseStatus.AWAITING_APPROVAL: frozenset(
        {
            CaseStatus.INVESTIGATING,
            CaseStatus.AWAITING_CUSTOMER,
            CaseStatus.ESCALATED,
            CaseStatus.RESOLVED,
            CaseStatus.ERROR,
        }
    ),
    CaseStatus.ESCALATED: frozenset(),
    CaseStatus.RESOLVED: frozenset(),
    CaseStatus.ERROR: frozenset({CaseStatus.ESCALATED}),
}


@dataclass(frozen=True)
class Violation:
    """A guard rejection: machine-readable ``code`` plus an explanation for the agent."""

    code: str
    message: str


@dataclass(frozen=True)
class OrderInsights:
    """Values derived from an order at read time (not persisted)."""

    days_late: int
    days_since_last_scan: int | None
    eligibility: dict[str, bool]


def parse_ts(value: str) -> datetime:
    """Parse an ISO 8601 date/datetime; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def order_insights(order: Order, now: datetime) -> OrderInsights:
    """Compute ``days_late``, ``days_since_last_scan`` and ``eligibility`` for an order."""
    open_with_courier = order.status in REDELIVERY_STATUSES

    days_late = 0
    if order.eta and order.status not in _CLOSED_ORDER_STATUSES:
        days_late = max(
            0, (now.date() - parse_ts(order.eta).astimezone(UTC).date()).days
        )

    days_since_last_scan: int | None = None
    if order.last_scan_at:
        days_since_last_scan = max(0, (now - parse_ts(order.last_scan_at)).days)

    lost = (
        open_with_courier
        and days_since_last_scan is not None
        and days_since_last_scan >= policy.LOST_THRESHOLD_DAYS
    )
    return OrderInsights(
        days_late=days_late,
        days_since_last_scan=days_since_last_scan,
        eligibility={
            "apology": days_late >= policy.DELAY_APOLOGY_DAYS,
            "voucher": days_late >= policy.DELAY_COMPENSATION_DAYS,
            "redelivery": open_with_courier,
            "refund_lost_package": lost,
            "escalate_not_received": order.status is OrderStatus.DELIVERED,
        },
    )


def owns_order(case: Case, order: Order) -> bool:
    return order.customer_id == case.customer_id


def check_status_transition(current: CaseStatus, new: CaseStatus) -> Violation | None:
    if current == new or new in _ALLOWED_TRANSITIONS[current]:
        return None
    return Violation(
        "invalid_transition",
        f"status kasus tidak boleh berubah dari {current} ke {new}",
    )


def check_message_body(body: str) -> Violation | None:
    text = body.strip()
    if not text:
        return Violation("invalid_input", "isi pesan kosong")
    if len(text) > MAX_MESSAGE_CHARS:
        return Violation(
            "invalid_input", f"isi pesan melebihi {MAX_MESSAGE_CHARS} karakter"
        )
    if _INTERNAL_ID_RE.search(text):
        return Violation(
            "internal_id_in_message", "pesan tidak boleh memuat ID internal"
        )
    return None


def check_voucher(
    amount_idr: int, insights: OrderInsights, case: Case
) -> Violation | None:
    if amount_idr <= 0 or amount_idr > policy.VOUCHER_MAX_IDR:
        return Violation(
            "amount_out_of_range",
            f"nilai voucher harus 1..{policy.VOUCHER_MAX_IDR} rupiah",
        )
    if case.resolution is not None and case.resolution.voucher_code:
        return Violation("voucher_already_issued", "kasus ini sudah mendapat voucher")
    if not insights.eligibility["voucher"]:
        return Violation(
            "not_eligible",
            f"voucher hanya untuk keterlambatan >= {policy.DELAY_COMPENSATION_DAYS} hari",
        )
    return None


def check_redelivery(order: Order) -> Violation | None:
    if order.status not in REDELIVERY_STATUSES:
        return Violation(
            "not_eligible",
            f"pengiriman ulang tidak bisa untuk pesanan berstatus {order.status}",
        )
    return None


def check_refund_request(
    amount_idr: int, order: Order, insights: OrderInsights
) -> Violation | None:
    if order.status is OrderStatus.REFUNDED:
        return Violation("already_refunded", "pesanan ini sudah direfund")
    if amount_idr <= 0 or amount_idr > order.total_idr:
        return Violation(
            "amount_out_of_range", f"nominal refund harus 1..{order.total_idr} rupiah"
        )
    if not insights.eligibility["refund_lost_package"]:
        return Violation(
            "not_eligible",
            "refund hanya untuk paket tanpa pembaruan tracking "
            f">= {policy.LOST_THRESHOLD_DAYS} hari",
        )
    return None


def refund_needs_approval(amount_idr: int) -> bool:
    return amount_idr > policy.AUTO_REFUND_LIMIT_IDR


def check_refund_execution(
    approval: Approval | None,
    *,
    case_id: str,
    order: Order,
    amount_idr: int,
) -> Violation | None:
    """Allow execution only with an ``approved`` approval matching case, order and amount."""
    required = "approval_required"
    if approval is None:
        return Violation(required, "approval tidak ditemukan")
    if approval.status is not ApprovalStatus.APPROVED:
        return Violation(
            required, f"approval berstatus {approval.status}, bukan approved"
        )
    if approval.case_id != case_id:
        return Violation(required, "approval bukan milik kasus ini")
    if approval.order_id != order.order_id:
        return Violation(required, "approval bukan untuk pesanan ini")
    if approval.amount_idr != amount_idr:
        return Violation(required, "nominal tidak sama dengan nominal yang disetujui")
    if amount_idr > order.total_idr:
        return Violation("amount_out_of_range", "nominal refund melebihi total pesanan")
    if order.status is OrderStatus.REFUNDED:
        return Violation(
            "already_executed", "refund untuk pesanan ini sudah dieksekusi"
        )
    return None


def _staff_tz() -> timezone | ZoneInfo:
    try:
        return ZoneInfo(policy.STAFF_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=7))  # WIB


def staff_on_duty(now: datetime) -> bool:
    hour = now.astimezone(_staff_tz()).hour
    return policy.STAFF_HOURS_START <= hour < policy.STAFF_HOURS_END
