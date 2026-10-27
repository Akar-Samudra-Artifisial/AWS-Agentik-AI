"""Pure guard functions and ``search_policy`` (KB retrieval + static fallback)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from _agent_support import NOW, iso
from botocore.stub import Stubber
from resolveai_common.models import CaseStatus, Order, OrderStatus

from agent.context import ToolContext
from agent.guards import (
    check_message_body,
    check_status_transition,
    order_insights,
    refund_needs_approval,
    staff_on_duty,
)
from agent.tools import build_tools
from agent.tools.policy_search import BedrockKnowledgeBaseRetriever, static_search


def _order(**kw: Any) -> Order:
    base: dict[str, Any] = {
        "order_id": "ORD-1",
        "customer_id": "CUST-1",
        "status": OrderStatus.IN_TRANSIT,
        "total_idr": 100_000,
        "created_at": iso(NOW - timedelta(days=10)),
    }
    return Order(**{**base, **kw})


def test_order_insights_lost_threshold() -> None:
    four = order_insights(_order(last_scan_at=iso(NOW - timedelta(days=4))), NOW)
    five = order_insights(_order(last_scan_at=iso(NOW - timedelta(days=5))), NOW)
    delivered = order_insights(
        _order(status=OrderStatus.DELIVERED, last_scan_at=iso(NOW - timedelta(days=9))),
        NOW,
    )

    assert four.eligibility["refund_lost_package"] is False
    assert five.eligibility["refund_lost_package"] is True
    assert delivered.eligibility["refund_lost_package"] is False
    assert delivered.eligibility["escalate_not_received"] is True


def test_order_insights_days_late_from_date_eta() -> None:
    insights = order_insights(_order(eta="2026-10-26"), NOW)
    assert insights.days_late == 2 and insights.eligibility["voucher"] is True
    assert order_insights(_order(eta="2026-10-30"), NOW).days_late == 0


def test_refund_needs_approval_boundary() -> None:
    assert refund_needs_approval(100_000) is False
    assert refund_needs_approval(100_001) is True


def test_status_transitions() -> None:
    assert check_status_transition(CaseStatus.OPEN, CaseStatus.INVESTIGATING) is None
    assert (
        check_status_transition(CaseStatus.RESOLVED, CaseStatus.INVESTIGATING)
        is not None
    )
    assert (
        check_status_transition(CaseStatus.ESCALATED, CaseStatus.RESOLVED) is not None
    )


def test_message_body_guard() -> None:
    assert check_message_body("Pesanan ORD-1001 untuk kasus CASE-20261028-0001") is None
    assert check_message_body("approval APR-12AB").code == "internal_id_in_message"
    assert check_message_body("   ").code == "invalid_input"


def test_staff_hours_wib() -> None:
    assert staff_on_duty(datetime(2026, 10, 28, 1, 0, tzinfo=UTC)) is True  # 08:00 WIB
    assert (
        staff_on_duty(datetime(2026, 10, 28, 13, 0, tzinfo=UTC)) is False
    )  # 20:00 WIB


# --------------------------------------------------------------------------- #
# search_policy
# --------------------------------------------------------------------------- #
def test_static_search_returns_sources_top4() -> None:
    results = static_search("refund di atas Rp100.000 perlu persetujuan staf")
    assert 0 < len(results) <= 4
    assert results[0]["source"] == "refund-policy"
    assert set(results[0]) == {"text", "source", "score"}


def test_search_policy_without_kb_uses_static_fallback(ctx: ToolContext) -> None:
    search = {fn.__name__: fn for fn in build_tools(ctx)}["search_policy"]
    result = search(query="kapan paket dianggap hilang")
    assert result["retrieval"] == "static_fallback"
    assert any(r["source"] == "lost-package-policy" for r in result["results"])


class _BrokenRetriever:
    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        raise TimeoutError("kb timeout")


def test_search_policy_falls_back_when_kb_fails(ctx: ToolContext) -> None:
    ctx.policy_retriever = _BrokenRetriever()
    search = {fn.__name__: fn for fn in build_tools(ctx)}["search_policy"]
    result = search(query="refund perlu persetujuan staf")
    assert result["ok"] is True and result["retrieval"] == "static_fallback"


def test_bedrock_retriever_maps_results(ctx: ToolContext) -> None:
    client = boto3.client("bedrock-agent-runtime", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "retrieve",
        {
            "retrievalResults": [
                {
                    "content": {
                        "text": "Refund di atas Rp100.000 wajib persetujuan staf."
                    },
                    "location": {
                        "type": "S3",
                        "s3Location": {"uri": "s3://kb-docs/refund-policy.md"},
                    },
                    "score": 0.81234,
                }
            ]
        },
        {
            "knowledgeBaseId": "KBTEST0001",
            "retrievalQuery": {"text": "refund besar"},
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {"numberOfResults": 4}
            },
        },
    )
    ctx.policy_retriever = BedrockKnowledgeBaseRetriever("KBTEST0001", client=client)
    search = {fn.__name__: fn for fn in build_tools(ctx)}["search_policy"]

    with stubber:
        result = search(query="refund besar")

    assert result["retrieval"] == "knowledge_base"
    assert result["results"] == [
        {
            "text": "Refund di atas Rp100.000 wajib persetujuan staf.",
            "source": "refund-policy",
            "score": 0.812,
        }
    ]
