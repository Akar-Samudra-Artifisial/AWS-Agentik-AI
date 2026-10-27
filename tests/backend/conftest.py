"""Fixtures for backend tests: moto DynamoDB tables, stub agent and stub sender.

``backend/`` is added to ``sys.path`` here (locally) so ``api``, ``dispatcher`` and
``services`` import the same way they do inside the Lambda bundle.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws
from resolveai_common.repository import (
    AGENT_EVENTS_SORT_KEY,
    MESSAGES_SORT_KEY,
    Repositories,
)

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend_helpers import API_KEY, StubInvoker, StubSender
from services.deps import Deps

PREFIX = "resolveai-test"


def _create_tables(dynamodb: Any) -> None:
    def table(
        name: str,
        hash_key: str,
        range_key: str | None = None,
        gsis: list[tuple[str, str, str | None]] | None = None,
    ) -> None:
        attrs = {hash_key, *([range_key] if range_key else [])}
        key_schema = [{"AttributeName": hash_key, "KeyType": "HASH"}]
        if range_key:
            key_schema.append({"AttributeName": range_key, "KeyType": "RANGE"})
        kwargs: dict[str, Any] = {}
        if gsis:
            indexes = []
            for index_name, pk, sk in gsis:
                attrs.add(pk)
                schema = [{"AttributeName": pk, "KeyType": "HASH"}]
                if sk:
                    attrs.add(sk)
                    schema.append({"AttributeName": sk, "KeyType": "RANGE"})
                indexes.append(
                    {
                        "IndexName": index_name,
                        "KeySchema": schema,
                        "Projection": {"ProjectionType": "ALL"},
                    }
                )
            kwargs["GlobalSecondaryIndexes"] = indexes
        dynamodb.create_table(
            TableName=f"{PREFIX}-{name}",
            KeySchema=key_schema,
            AttributeDefinitions=[
                {"AttributeName": a, "AttributeType": "S"} for a in sorted(attrs)
            ],
            BillingMode="PAY_PER_REQUEST",
            **kwargs,
        )

    table("customers", "customer_id", gsis=[("by_phone", "phone_e164", None)])
    table("orders", "order_id", gsis=[("by_customer", "customer_id", "created_at")])
    table(
        "cases",
        "case_id",
        gsis=[
            ("by_customer", "customer_id", "updated_at"),
            ("by_status", "status", "updated_at"),
        ],
    )
    table("messages", "case_id", MESSAGES_SORT_KEY)
    table("agent_events", "case_id", AGENT_EVENTS_SORT_KEY)
    table("approvals", "approval_id", gsis=[("by_status", "status", "requested_at")])
    table("processed_events", "event_id")


@pytest.fixture
def aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("RESOLVEAI_TABLE_PREFIX", PREFIX)
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.delenv("DISPATCHER_FUNCTION_NAME", raising=False)


@pytest.fixture
def deps(aws_env: None) -> Iterator[Deps]:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(dynamodb)
        yield Deps(
            dynamodb=dynamodb,
            repos=Repositories(prefix=PREFIX, dynamodb=dynamodb),
            invoker=StubInvoker(),
            sender=StubSender(),
        )


@pytest.fixture
def invoker(deps: Deps) -> StubInvoker:
    assert isinstance(deps.invoker, StubInvoker)
    return deps.invoker


@pytest.fixture
def sender(deps: Deps) -> StubSender:
    assert isinstance(deps.sender, StubSender)
    return deps.sender
