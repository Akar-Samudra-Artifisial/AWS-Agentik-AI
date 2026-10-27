"""Order lookup tools: ``get_order`` and ``find_orders_by_customer``.

Annotations are evaluated eagerly (no ``from __future__ import annotations``) so the
tool schema derived from the signature uses real types.
"""

from typing import Any

from resolveai_common.models import Order

from ..context import ToolContext
from ..guards import order_insights
from .base import ok
from .core import load_case, load_owned_order, update_case_fields
from .registry import logged_tool

__all__ = ["find_orders_by_customer", "get_order"]

RECENT_ORDERS_LIMIT = 5


def _order_view(order: Order) -> dict[str, Any]:
    # customer_id is an internal identifier; never hand it to the model.
    return order.model_dump(mode="json", exclude_none=True, exclude={"customer_id"})


@logged_tool
def get_order(ctx: ToolContext, order_id: str) -> dict[str, Any]:
    """Ambil detail satu pesanan milik pelanggan kasus ini.

    Get one order of this case's customer, with derived values computed now:
    ``days_late`` (days past ETA), ``days_since_last_scan`` and ``eligibility`` flags
    (apology, voucher, redelivery, refund_lost_package, escalate_not_received).
    Call this before telling the customer anything about the order.

    Args:
        order_id: Order ID as given by the customer, e.g. "ORD-1001".

    Returns:
        ``{ok, order, days_late, days_since_last_scan, eligibility}`` or
        ``{ok: false, error: {code: "not_found"}}`` if the order does not exist or
        belongs to someone else. Payment and courier are simulated.
    """
    case = load_case(ctx)
    order = load_owned_order(ctx, case, order_id)
    insights = order_insights(order, ctx.now())
    if case.order_id is None:
        update_case_fields(ctx, order_id=order.order_id)
    return ok(
        order=_order_view(order),
        days_late=insights.days_late,
        days_since_last_scan=insights.days_since_last_scan,
        eligibility=insights.eligibility,
        simulated_courier_and_payment=True,
    )


@logged_tool
def find_orders_by_customer(ctx: ToolContext) -> dict[str, Any]:
    """Daftar 5 pesanan terakhir milik pelanggan kasus ini (ringkas).

    Use when the customer did not mention an order ID. If the list is empty or it is
    unclear which order they mean, ask the customer for the order ID instead of guessing.

    Returns:
        ``{ok, orders: [{order_id, status, total_idr, created_at, eta, courier, items}]}``
        newest first.
    """
    case = load_case(ctx)
    orders = ctx.repos.orders.find_by_customer(case.customer_id)[:RECENT_ORDERS_LIMIT]
    return ok(
        orders=[
            {
                "order_id": o.order_id,
                "status": str(o.status),
                "total_idr": o.total_idr,
                "created_at": o.created_at,
                "eta": o.eta,
                "courier": o.courier,
                "items": [item.name for item in o.items],
            }
            for o in orders
        ]
    )
