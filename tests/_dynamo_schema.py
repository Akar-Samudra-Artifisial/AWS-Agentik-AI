"""DynamoDB table definitions for moto-backed tests.

Mirrors the schema in ``docs/prd/00-overview.md`` §10 (PKs, SKs, GSIs) so repository and
agent-tool tests run against tables shaped like production. Test-only helper.
"""

from __future__ import annotations

from typing import Any

_S = "S"


def _gsi(name: str, pk: str, sk: str | None = None) -> dict[str, Any]:
    schema = [{"AttributeName": pk, "KeyType": "HASH"}]
    if sk:
        schema.append({"AttributeName": sk, "KeyType": "RANGE"})
    return {
        "IndexName": name,
        "KeySchema": schema,
        "Projection": {"ProjectionType": "ALL"},
    }


# table suffix -> (pk, sk, gsis)
TABLES: dict[str, tuple[str, str | None, list[dict[str, Any]]]] = {
    "customers": ("customer_id", None, [_gsi("by_phone", "phone_e164")]),
    "orders": ("order_id", None, [_gsi("by_customer", "customer_id", "created_at")]),
    "cases": (
        "case_id",
        None,
        [
            _gsi("by_customer", "customer_id", "updated_at"),
            _gsi("by_status", "status", "updated_at"),
        ],
    ),
    "messages": ("case_id", "sk", []),
    "agent_events": ("case_id", "sk", []),
    "approvals": ("approval_id", None, [_gsi("by_status", "status", "requested_at")]),
    "processed_events": ("event_id", None, []),
}


def create_tables(resource: Any, prefix: str) -> None:
    """Create every ResolveAI table (on-demand billing) under ``<prefix>-<table>``."""
    for suffix, (pk, sk, gsis) in TABLES.items():
        key_schema = [{"AttributeName": pk, "KeyType": "HASH"}]
        attrs = {pk}
        if sk:
            key_schema.append({"AttributeName": sk, "KeyType": "RANGE"})
            attrs.add(sk)
        for gsi in gsis:
            attrs.update(k["AttributeName"] for k in gsi["KeySchema"])
        kwargs: dict[str, Any] = {
            "TableName": f"{prefix}-{suffix}",
            "KeySchema": key_schema,
            "AttributeDefinitions": [
                {"AttributeName": a, "AttributeType": _S} for a in attrs
            ],
            "BillingMode": "PAY_PER_REQUEST",
        }
        if gsis:
            kwargs["GlobalSecondaryIndexes"] = gsis
        resource.create_table(**kwargs)
