"""Case state tools: ``update_case`` and ``escalate_to_human``."""

from typing import Any, Literal

from resolveai_common.models import (
    Case,
    CaseCategory,
    CasePriority,
    CaseStatus,
    ResolutionType,
)

from ..context import ToolContext
from ..guards import check_status_transition
from .base import ToolError, ok
from .core import escalate_case, load_case, update_case_fields
from .registry import logged_tool

__all__ = ["escalate_to_human", "update_case"]

MAX_SUMMARY_CHARS = 500
MAX_REASON_CHARS = 300

AgentCaseStatus = Literal[
    "investigating", "awaiting_customer", "awaiting_approval", "resolved"
]
CategoryName = Literal[
    "late_delivery",
    "lost_package",
    "not_received",
    "status_inquiry",
    "address_change",
    "other",
]
PriorityName = Literal["normal", "high"]
AgentResolutionType = Literal["auto_resolved", "approved_by_staff", "rejected_by_staff"]


def case_view(case: Case) -> dict[str, Any]:
    return case.model_dump(
        mode="json",
        exclude_none=True,
        include={
            "case_id",
            "order_id",
            "channel",
            "status",
            "category",
            "priority",
            "resolution_type",
            "resolution",
            "summary",
        },
    )


@logged_tool
def update_case(
    ctx: ToolContext,
    status: AgentCaseStatus | None = None,
    category: CategoryName | None = None,
    priority: PriorityName | None = None,
    summary: str | None = None,
    resolution_type: AgentResolutionType | None = None,
) -> dict[str, Any]:
    """Perbarui kasus yang sedang ditangani (status, kategori, prioritas, ringkasan).

    Update the current case. Status transitions are validated (resolved/escalated cases
    cannot be reopened). Use escalate_to_human, not this tool, to escalate. Setting
    status "resolved" records the resolution time; resolution_type defaults to
    "auto_resolved".

    Args:
        status: New status: investigating, awaiting_customer, awaiting_approval, resolved.
        category: Complaint category derived from the order data.
        priority: "normal" or "high".
        summary: Short internal case summary (max 500 characters).
        resolution_type: How the case was resolved (only with status "resolved").

    Returns:
        ``{ok, case}`` with the updated case.
    """
    case = load_case(ctx)
    updates: dict[str, Any] = {}
    if status is not None:
        new_status = CaseStatus(status)
        violation = check_status_transition(case.status, new_status)
        if violation:
            raise ToolError.from_violation(violation)
        updates["status"] = new_status
        if new_status is CaseStatus.RESOLVED:
            updates["resolved_at"] = ctx.now_iso()
            updates["resolution_type"] = ResolutionType(
                resolution_type or "auto_resolved"
            )
    if resolution_type is not None and status != "resolved":
        raise ToolError(
            "invalid_input", "resolution_type hanya boleh bersama status resolved"
        )
    if category is not None:
        updates["category"] = CaseCategory(category)
    if priority is not None:
        updates["priority"] = CasePriority(priority)
    if summary is not None:
        if len(summary) > MAX_SUMMARY_CHARS:
            raise ToolError(
                "invalid_input", f"summary melebihi {MAX_SUMMARY_CHARS} karakter"
            )
        updates["summary"] = summary.strip()
    if not updates:
        raise ToolError("invalid_input", "tidak ada field yang diperbarui")
    return ok(case=case_view(update_case_fields(ctx, **updates)))


@logged_tool
def escalate_to_human(
    ctx: ToolContext, reason: str, priority: PriorityName = "normal"
) -> dict[str, Any]:
    """Teruskan kasus ke staf manusia dan beri tahu pelanggan.

    Escalate this case to human staff: sets status "escalated", records the reason in
    the timeline and sends the customer a holding message (mentions staff hours
    08.00-20.00 WIB when outside them). Use for legal/media threats, fraud accusations,
    repeated abuse, "delivered but not received", order not found after asking twice,
    or anything outside policy. Use priority "high" for threats/fraud.

    Args:
        reason: Why the case is escalated (internal, max 300 characters).
        priority: "normal" or "high".

    Returns:
        ``{ok, escalated, priority, staff_on_duty, customer_notified}``.
    """
    reason = reason.strip()
    if not reason or len(reason) > MAX_REASON_CHARS:
        raise ToolError(
            "invalid_input", f"reason wajib diisi, maks {MAX_REASON_CHARS} karakter"
        )
    return ok(**escalate_case(ctx, reason, CasePriority(priority), notify=True))
