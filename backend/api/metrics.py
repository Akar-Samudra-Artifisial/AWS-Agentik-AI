"""Aggregate metrics (``02-backend.md`` §6), computed in memory from full scans."""

from __future__ import annotations

import math
from collections.abc import Sequence

from resolveai_common.models import (
    Approval,
    ApprovalStatus,
    Case,
    CaseCategory,
    CaseStatus,
    Channel,
    DeliveryStatus,
    Message,
    MessageDirection,
    ResolutionType,
)
from services.config import parse_iso

from .schemas import FirstResponseMs, Metrics, ResolutionMs, Totals

__all__ = ["compute_metrics", "percentile"]

_ACTIVE = frozenset(
    {
        CaseStatus.OPEN,
        CaseStatus.INVESTIGATING,
        CaseStatus.AWAITING_CUSTOMER,
        CaseStatus.AWAITING_APPROVAL,
    }
)
_SENT = frozenset({DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.READ})


def percentile(values: Sequence[int], pct: float) -> int:
    """Nearest-rank percentile; ``0`` for an empty sequence."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _elapsed_ms(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    delta = parse_iso(end) - parse_iso(start)
    return max(0, int(delta.total_seconds() * 1000))


def compute_metrics(
    cases: Sequence[Case], approvals: Sequence[Approval], messages: Sequence[Message]
) -> Metrics:
    """Build the metrics document; seeded data is counted like live data."""
    totals = Totals(
        cases=len(cases),
        active=sum(1 for c in cases if c.status in _ACTIVE),
        resolved=sum(1 for c in cases if c.status is CaseStatus.RESOLVED),
        escalated=sum(1 for c in cases if c.status is CaseStatus.ESCALATED),
        pending_approvals=sum(
            1 for a in approvals if a.status is ApprovalStatus.PENDING
        ),
    )
    closed = totals.resolved + totals.escalated
    auto = sum(1 for c in cases if c.resolution_type is ResolutionType.AUTO_RESOLVED)
    rate = round(auto / closed, 4) if closed else 0.0

    first_response = [
        ms
        for c in cases
        if (ms := _elapsed_ms(c.first_inbound_at, c.first_response_at)) is not None
    ]
    resolution = [
        ms
        for c in cases
        if (ms := _elapsed_ms(c.first_inbound_at, c.resolved_at)) is not None
    ]

    by_channel = {ch.value: 0 for ch in Channel}
    by_category = {cat.value: 0 for cat in CaseCategory}
    for c in cases:
        by_channel[c.channel.value] += 1
        by_category[c.category.value] += 1

    messages_sent = {ch.value: 0 for ch in Channel}
    for m in messages:
        if m.direction is MessageDirection.OUTBOUND and m.delivery_status in _SENT:
            messages_sent[m.channel.value] += 1

    return Metrics(
        totals=totals,
        auto_resolution_rate=rate,
        first_response_ms=FirstResponseMs(
            p50=percentile(first_response, 50), p90=percentile(first_response, 90)
        ),
        resolution_ms=ResolutionMs(p50=percentile(resolution, 50)),
        by_channel=by_channel,
        by_category=by_category,
        messages_sent=messages_sent,
    )
