"""Compensation/action tools: voucher, redelivery and the two-step refund.

Payment and courier are SIMULATED: these tools only update DynamoDB records. The
sensitive refund path is guarded in code — ``execute_refund`` requires an ``approved``
approval matching case, order and amount, and executes at most once (conditional
update on the order).
"""

import secrets
import string
import uuid
from datetime import date, timedelta
from typing import Any

from botocore.exceptions import ClientError
from resolveai_common.models import (
    Approval,
    ApprovalStatus,
    CaseResolution,
    OrderStatus,
    RefundInfo,
)

from ..context import ToolContext
from ..guards import (
    check_redelivery,
    check_refund_execution,
    check_refund_request,
    check_voucher,
    order_insights,
    refund_needs_approval,
)
from .base import ToolError, ok
from .core import load_case, load_owned_order, update_case_fields
from .registry import logged_tool

__all__ = ["create_voucher", "execute_refund", "request_refund", "schedule_redelivery"]

VOUCHER_PREFIX = "RAI-"
_VOUCHER_ALPHABET = string.ascii_uppercase + string.digits
MAX_REDELIVERY_DAYS_AHEAD = 14
# Redeliveries are booked for 09:00 WIB (02:00 UTC) on the chosen date.
_REDELIVERY_TIME_UTC = "T02:00:00Z"
MAX_REASON_CHARS = 300


def _rupiah(amount_idr: int) -> str:
    return "Rp" + f"{amount_idr:,}".replace(",", ".")


def _is_conditional_failure(exc: ClientError) -> bool:
    return exc.response["Error"]["Code"] == "ConditionalCheckFailedException"


@logged_tool
def create_voucher(ctx: ToolContext, amount_idr: int) -> dict[str, Any]:
    """Buat voucher kompensasi keterlambatan untuk kasus ini.

    Create a compensation voucher (code "RAI-XXXXXX") for a late order. Only allowed
    when the case order is at least 2 days late, amount at most Rp25.000, and only one
    voucher per case. Call get_order first so the case is linked to its order.

    Args:
        amount_idr: Voucher value in integer rupiah (max 25000).

    Returns:
        ``{ok, voucher_code, amount_idr}``.
    """
    case = load_case(ctx)
    if case.order_id is None:
        raise ToolError(
            "order_required", "panggil get_order dulu untuk menautkan pesanan"
        )
    order = load_owned_order(ctx, case, case.order_id)
    violation = check_voucher(amount_idr, order_insights(order, ctx.now()), case)
    if violation:
        raise ToolError.from_violation(violation)

    code = VOUCHER_PREFIX + "".join(secrets.choice(_VOUCHER_ALPHABET) for _ in range(6))
    resolution = CaseResolution(
        action="voucher",
        amount_idr=amount_idr,
        voucher_code=code,
        summary=f"Voucher {_rupiah(amount_idr)} untuk keterlambatan pesanan {order.order_id}",
    )
    try:
        ctx.table(ctx.repos.cases).update_item(
            Key={"case_id": case.case_id},
            UpdateExpression="SET resolution = :res, updated_at = :now",
            ConditionExpression=(
                "attribute_exists(case_id) AND (attribute_not_exists(resolution) "
                "OR attribute_not_exists(resolution.voucher_code))"
            ),
            ExpressionAttributeValues={
                ":res": resolution.model_dump(mode="json", exclude_none=True),
                ":now": ctx.now_iso(),
            },
        )
    except ClientError as exc:
        if _is_conditional_failure(exc):
            raise ToolError(
                "voucher_already_issued", "kasus ini sudah mendapat voucher"
            ) from exc
        raise
    return ok(voucher_code=code, amount_idr=amount_idr)


@logged_tool
def schedule_redelivery(
    ctx: ToolContext, order_id: str, preferred_date: str | None = None
) -> dict[str, Any]:
    """Jadwalkan ulang pengiriman prioritas (simulasi kurir).

    Schedule a priority redelivery for an order still with the courier (status
    shipped, in_transit or out_for_delivery). The courier integration is simulated.

    Args:
        order_id: Order ID, e.g. "ORD-1001".
        preferred_date: Optional date "YYYY-MM-DD" between tomorrow and 14 days ahead;
            defaults to tomorrow.

    Returns:
        ``{ok, order_id, redelivery_at, simulated: true}``.
    """
    case = load_case(ctx)
    order = load_owned_order(ctx, case, order_id)
    violation = check_redelivery(order)
    if violation:
        raise ToolError.from_violation(violation)

    today = ctx.now().date()
    if preferred_date is None:
        target = today + timedelta(days=1)
    else:
        try:
            target = date.fromisoformat(preferred_date.strip())
        except ValueError as exc:
            raise ToolError(
                "invalid_input", "preferred_date harus berformat YYYY-MM-DD"
            ) from exc
        if not today < target <= today + timedelta(days=MAX_REDELIVERY_DAYS_AHEAD):
            raise ToolError(
                "invalid_input",
                f"preferred_date harus antara besok dan {MAX_REDELIVERY_DAYS_AHEAD} hari ke depan",
            )

    redelivery_at = target.isoformat() + _REDELIVERY_TIME_UTC
    ctx.repos.orders.put(order.model_copy(update={"redelivery_at": redelivery_at}))
    if case.resolution is None:
        update_case_fields(
            ctx,
            resolution=CaseResolution(
                action="redelivery",
                summary=f"Pengiriman ulang prioritas {order.order_id} pada {target.isoformat()}",
            ),
        )
    return ok(order_id=order.order_id, redelivery_at=redelivery_at, simulated=True)


def _active_refund_approval(
    ctx: ToolContext, case_id: str, order_id: str
) -> Approval | None:
    for status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED):
        for approval in ctx.repos.approvals.find_by_status(status):
            if approval.case_id == case_id and approval.order_id == order_id:
                return approval
    return None


@logged_tool
def request_refund(
    ctx: ToolContext, order_id: str, amount_idr: int, reason: str
) -> dict[str, Any]:
    """Ajukan refund untuk pesanan yang hilang (pembayaran simulasi).

    Request a refund for an order considered lost (no tracking update for at least
    5 days). Amounts up to Rp100.000 are approved automatically by policy
    (status "auto_approved"; then call execute_refund). Larger amounts create a
    pending staff approval (status "pending_approval"): tell the customer it is being
    verified by the team and do NOT promise the refund. Repeating the request for the
    same order returns the existing approval.

    Args:
        order_id: Order ID, e.g. "ORD-1002".
        amount_idr: Refund amount in integer rupiah, at most the order total.
        reason: Short reason (max 300 characters).

    Returns:
        ``{ok, status: "auto_approved" | "pending_approval", approval_id, amount_idr}``.
    """
    reason = reason.strip()
    if not reason or len(reason) > MAX_REASON_CHARS:
        raise ToolError(
            "invalid_input", f"reason wajib diisi, maks {MAX_REASON_CHARS} karakter"
        )
    case = load_case(ctx)
    order = load_owned_order(ctx, case, order_id)
    violation = check_refund_request(
        amount_idr, order, order_insights(order, ctx.now())
    )
    if violation:
        raise ToolError.from_violation(violation)

    existing = _active_refund_approval(ctx, case.case_id, order.order_id)
    if existing is not None:
        return ok(
            status=_refund_status(existing.status),
            approval_id=existing.approval_id,
            amount_idr=existing.amount_idr,
            duplicate=True,
        )

    now = ctx.now_iso()
    needs_staff = refund_needs_approval(amount_idr)
    approval = Approval(
        approval_id=f"APR-{uuid.uuid4().hex[:10].upper()}",
        case_id=case.case_id,
        order_id=order.order_id,
        amount_idr=amount_idr,
        reason=reason,
        status=ApprovalStatus.PENDING if needs_staff else ApprovalStatus.APPROVED,
        requested_at=now,
        decided_at=None if needs_staff else now,
        decided_by=None if needs_staff else "policy",
    )
    ctx.repos.approvals.put(approval)
    ctx.repos.orders.put(
        order.model_copy(
            update={
                "refund": RefundInfo(
                    status=approval.status, amount_idr=amount_idr, at=now
                )
            }
        )
    )
    return ok(
        status=_refund_status(approval.status),
        approval_id=approval.approval_id,
        amount_idr=amount_idr,
    )


def _refund_status(status: ApprovalStatus) -> str:
    return "pending_approval" if status is ApprovalStatus.PENDING else "auto_approved"


@logged_tool
def execute_refund(
    ctx: ToolContext, approval_id: str, order_id: str, amount_idr: int
) -> dict[str, Any]:
    """Eksekusi refund yang SUDAH disetujui (pembayaran simulasi).

    Execute a refund only after its approval is "approved" (auto-approved by policy or
    approved by staff). The approval must belong to this case and match the order and
    amount exactly; otherwise the result is error "approval_required". A refund is
    executed at most once. The payment itself is simulated.

    Args:
        approval_id: Approval ID returned by request_refund.
        order_id: Order ID the approval is for.
        amount_idr: Approved amount in integer rupiah.

    Returns:
        ``{ok, status: "executed", amount_idr, simulated: true}``.
    """
    case = load_case(ctx)
    order = load_owned_order(ctx, case, order_id)
    approval = ctx.repos.approvals.get(approval_id.strip())
    violation = check_refund_execution(
        approval, case_id=case.case_id, order=order, amount_idr=amount_idr
    )
    if violation:
        raise ToolError.from_violation(violation)

    now = ctx.now_iso()
    try:
        ctx.table(ctx.repos.orders).update_item(
            Key={"order_id": order.order_id},
            UpdateExpression="SET #st = :refunded, refund = :refund",
            ConditionExpression="attribute_exists(order_id) AND #st <> :refunded",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":refunded": OrderStatus.REFUNDED.value,
                ":refund": RefundInfo(
                    status=ApprovalStatus.APPROVED, amount_idr=amount_idr, at=now
                ).model_dump(mode="json"),
            },
        )
    except ClientError as exc:
        if _is_conditional_failure(exc):
            raise ToolError(
                "already_executed", "refund untuk pesanan ini sudah dieksekusi"
            ) from exc
        raise

    update_case_fields(
        ctx,
        resolution=CaseResolution(
            action="refund",
            amount_idr=amount_idr,
            summary=(
                f"Refund {_rupiah(amount_idr)} untuk pesanan {order.order_id} diproses ke "
                "metode pembayaran asal (simulasi), 3-5 hari kerja"
            ),
        ),
    )
    return ok(status="executed", amount_idr=amount_idr, simulated=True)
