"""DynamoDB repository layer for ResolveAI.

One repository class per table (``customers``, ``orders``, ``cases``, ``messages``,
``agent_events``, ``approvals``, ``processed_events``) wrapping get/put/update/query
with pydantic models (``models.py``) as the boundary type. Mirrors the schema and GSIs
in ``docs/prd/00-overview.md`` §10 and requirement BE-002 in ``docs/prd/02-backend.md``.

Conventions:
  - DynamoDB numbers are ``Decimal``; this module converts ``Decimal`` <-> ``int``
    on the way out/in so callers only ever see Python ``int`` (money is integer rupiah).
  - Items are written as JSON-safe dicts (``model_dump``), with ``None`` fields dropped
    because DynamoDB rejects null attribute values for indexed/sort keys and keeps items
    lean.
  - Table names come from the environment (``RESOLVEAI_TABLE_PREFIX``, default
    ``resolveai-dev``) or an explicit constructor argument. Region is never hardcoded;
    boto3 resolves it from the standard chain.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

from .models import (
    AgentEvent,
    Approval,
    ApprovalStatus,
    Case,
    CaseStatus,
    Customer,
    Message,
    Order,
    ProcessedEvent,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

__all__ = [
    "DEFAULT_TABLE_PREFIX",
    "AGENT_EVENTS_SORT_KEY",
    "MESSAGES_SORT_KEY",
    "to_dynamo",
    "from_dynamo",
    "CaseLockedError",
    "CaseNotFoundError",
    "DuplicateEventError",
    "Repositories",
    "CustomerRepository",
    "OrderRepository",
    "CaseRepository",
    "MessageRepository",
    "AgentEventRepository",
    "ApprovalRepository",
    "ProcessedEventRepository",
]

DEFAULT_TABLE_PREFIX = "resolveai-dev"

# Sort key attribute names; must match the deployed tables (infra/stacks/data_stack.py).
MESSAGES_SORT_KEY = "ts#msg_id"
AGENT_EVENTS_SORT_KEY = "ts#seq"

# Case lock time-to-live in seconds (BE-007: lock per case via conditional update).
CASE_LOCK_TTL_SECONDS = 150


class CaseLockedError(RuntimeError):
    """Raised when a case lock cannot be acquired because it is already held."""


class CaseNotFoundError(LookupError):
    """Raised when an operation targets a case that does not exist."""


class DuplicateEventError(RuntimeError):
    """Raised when an inbound event has already been processed (dedupe hit)."""


# --------------------------------------------------------------------------- #
# Decimal <-> int conversion (DynamoDB stores all numbers as Decimal)
# --------------------------------------------------------------------------- #


def to_dynamo(value: Any) -> Any:
    """Recursively convert a Python value into a DynamoDB-safe structure.

    ``int`` stays ``int`` (boto3's resource layer serializes it as a number),
    ``float`` is rejected by boto3, so this is defensive only. ``None`` values are
    dropped by the repositories before this is called; nested dicts/lists recurse.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        # DynamoDB resource layer cannot serialize float; callers must use int.
        raise TypeError("float is not supported in DynamoDB items; use int rupiah")
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def from_dynamo(value: Any) -> Any:
    """Recursively convert a DynamoDB item into plain Python types.

    DynamoDB numbers come back as ``Decimal``; integral decimals become ``int`` and any
    non-integral decimal (not expected in this schema) becomes ``float`` so pydantic can
    still validate it.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_dynamo(v) for v in value]
    return value


def _dump(model: Any) -> dict[str, Any]:
    """Serialize a pydantic model to a DynamoDB item, dropping ``None`` attributes."""
    return to_dynamo(model.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Repositories
# --------------------------------------------------------------------------- #


class _BaseRepository:
    """Shared helpers bound to a single DynamoDB table resource."""

    def __init__(self, table: Table) -> None:
        self._table = table

    @property
    def table_name(self) -> str:
        return self._table.name

    def _get(self, key: dict[str, Any]) -> dict[str, Any] | None:
        resp = self._table.get_item(Key=key)
        item = resp.get("Item")
        return from_dynamo(item) if item is not None else None

    def _query_all(self, max_items: int | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        """Run a paginated Query and return items as plain Python.

        ``max_items`` caps the total across pages (DynamoDB ``Limit`` is per page only).
        """
        items: list[dict[str, Any]] = []
        resp = self._table.query(**kwargs)
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp and (max_items is None or len(items) < max_items):
            resp = self._table.query(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
            items.extend(resp.get("Items", []))
        if max_items is not None:
            items = items[:max_items]
        return [from_dynamo(item) for item in items]


class CustomerRepository(_BaseRepository):
    """``customers`` table. PK ``customer_id``; GSI ``by_phone`` on ``phone_e164``."""

    def get(self, customer_id: str) -> Customer | None:
        item = self._get({"customer_id": customer_id})
        return Customer.model_validate(item) if item else None

    def put(self, customer: Customer) -> None:
        self._table.put_item(Item=_dump(customer))

    def find_by_phone(self, phone_e164: str) -> Customer | None:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            IndexName="by_phone",
            KeyConditionExpression=Key("phone_e164").eq(phone_e164),
        )
        return Customer.model_validate(items[0]) if items else None


class OrderRepository(_BaseRepository):
    """``orders`` table. PK ``order_id``; GSI ``by_customer`` (``customer_id``, ``created_at``)."""

    def get(self, order_id: str) -> Order | None:
        item = self._get({"order_id": order_id})
        return Order.model_validate(item) if item else None

    def put(self, order: Order) -> None:
        self._table.put_item(Item=_dump(order))

    def find_by_customer(self, customer_id: str) -> list[Order]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            IndexName="by_customer",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            ScanIndexForward=False,
        )
        return [Order.model_validate(item) for item in items]


class CaseRepository(_BaseRepository):
    """``cases`` table. PK ``case_id``; GSIs ``by_customer`` and ``by_status``."""

    def get(self, case_id: str) -> Case | None:
        item = self._get({"case_id": case_id})
        return Case.model_validate(item) if item else None

    def put(self, case: Case) -> None:
        self._table.put_item(Item=_dump(case))

    def find_by_customer(self, customer_id: str) -> list[Case]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            IndexName="by_customer",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            ScanIndexForward=False,
        )
        return [Case.model_validate(item) for item in items]

    def find_by_status(self, status: CaseStatus | str) -> list[Case]:
        from boto3.dynamodb.conditions import Key

        status_value = status.value if isinstance(status, CaseStatus) else status
        items = self._query_all(
            IndexName="by_status",
            KeyConditionExpression=Key("status").eq(status_value),
            ScanIndexForward=False,
        )
        return [Case.model_validate(item) for item in items]

    def acquire_lock(self, case_id: str, lock_until: str, now: str) -> None:
        """Acquire a case lock via a conditional update (BE-007).

        Sets ``lock_until`` and ``updated_at`` only if the case exists and is currently
        unlocked or the existing lock has expired (``lock_until < now``). A missing case
        is never created.

        Args:
            case_id: Case to lock.
            lock_until: New ISO 8601 UTC lock expiry (``now`` + ``CASE_LOCK_TTL_SECONDS``).
            now: Current ISO 8601 UTC timestamp, compared against any existing lock.

        Raises:
            CaseNotFoundError: if the case does not exist.
            CaseLockedError: if a non-expired lock is already held.
        """
        try:
            self._table.update_item(
                Key={"case_id": case_id},
                UpdateExpression="SET lock_until = :lu, updated_at = :now",
                ConditionExpression=(
                    "attribute_exists(case_id) AND (attribute_not_exists(lock_until)"
                    " OR lock_until = :null OR lock_until < :now)"
                ),
                ExpressionAttributeValues={":lu": lock_until, ":now": now, ":null": None},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                if self._get({"case_id": case_id}) is None:
                    raise CaseNotFoundError(f"case {case_id} does not exist") from exc
                raise CaseLockedError(f"case {case_id} is already locked") from exc
            raise

    def release_lock(self, case_id: str, now: str) -> None:
        """Release a case lock by clearing ``lock_until``."""
        self._table.update_item(
            Key={"case_id": case_id},
            UpdateExpression="REMOVE lock_until SET updated_at = :now",
            ExpressionAttributeValues={":now": now},
        )


class MessageRepository(_BaseRepository):
    """``messages`` table. PK ``case_id``, SK ``ts#msg_id`` (``MESSAGES_SORT_KEY``)."""

    @staticmethod
    def _sort_key(message: Message) -> str:
        return f"{message.ts}#{message.msg_id}"

    def put(self, message: Message) -> None:
        item = _dump(message)
        item[MESSAGES_SORT_KEY] = self._sort_key(message)
        self._table.put_item(Item=item)

    def list_for_case(
        self, case_id: str, limit: int | None = None, *, newest: bool = False
    ) -> list[Message]:
        """Return messages for a case in chronological order (oldest first).

        Args:
            case_id: Case whose messages are listed.
            limit: Maximum number of messages to return.
            newest: When ``True`` with ``limit``, return the latest ``limit`` messages
                (still oldest first) instead of the earliest ones.
        """
        from boto3.dynamodb.conditions import Key

        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("case_id").eq(case_id),
            "ScanIndexForward": not newest,
        }
        if limit is not None:
            kwargs["Limit"] = limit
        items = self._query_all(max_items=limit, **kwargs)
        if newest:
            items.reverse()
        return [
            Message.model_validate({k: v for k, v in item.items() if k != MESSAGES_SORT_KEY})
            for item in items
        ]


class AgentEventRepository(_BaseRepository):
    """``agent_events`` table. PK ``case_id``, SK ``ts#seq`` (``AGENT_EVENTS_SORT_KEY``)."""

    @staticmethod
    def _sort_key(event: AgentEvent) -> str:
        return f"{event.ts}#{event.seq:06d}"

    def put(self, event: AgentEvent) -> None:
        item = _dump(event)
        item[AGENT_EVENTS_SORT_KEY] = self._sort_key(event)
        self._table.put_item(Item=item)

    def list_for_case(self, case_id: str) -> list[AgentEvent]:
        from boto3.dynamodb.conditions import Key

        items = self._query_all(
            KeyConditionExpression=Key("case_id").eq(case_id),
            ScanIndexForward=True,
        )
        return [
            AgentEvent.model_validate(
                {k: v for k, v in item.items() if k != AGENT_EVENTS_SORT_KEY}
            )
            for item in items
        ]


class ApprovalRepository(_BaseRepository):
    """``approvals`` table. PK ``approval_id``; GSI ``by_status`` (``status``, ``requested_at``)."""

    def get(self, approval_id: str) -> Approval | None:
        item = self._get({"approval_id": approval_id})
        return Approval.model_validate(item) if item else None

    def put(self, approval: Approval) -> None:
        self._table.put_item(Item=_dump(approval))

    def find_by_status(self, status: ApprovalStatus | str) -> list[Approval]:
        from boto3.dynamodb.conditions import Key

        status_value = status.value if isinstance(status, ApprovalStatus) else status
        items = self._query_all(
            IndexName="by_status",
            KeyConditionExpression=Key("status").eq(status_value),
            ScanIndexForward=False,
        )
        return [Approval.model_validate(item) for item in items]


class ProcessedEventRepository(_BaseRepository):
    """``processed_events`` table. PK ``event_id`` with TTL for inbound dedupe."""

    def mark_processed(self, event: ProcessedEvent) -> None:
        """Record an event id, failing if it was already processed (idempotency).

        Uses a conditional ``put_item`` with ``attribute_not_exists(event_id)`` so a
        duplicated at-least-once delivery is rejected rather than reprocessed.

        Raises:
            DuplicateEventError: if the event id already exists.
        """
        try:
            self._table.put_item(
                Item=_dump(event),
                ConditionExpression="attribute_not_exists(event_id)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateEventError(f"event {event.event_id} already processed") from exc
            raise

    def exists(self, event_id: str) -> bool:
        return self._get({"event_id": event_id}) is not None


# --------------------------------------------------------------------------- #
# Aggregate accessor
# --------------------------------------------------------------------------- #


def _table_name(prefix: str, suffix: str) -> str:
    return f"{prefix}-{suffix}"


class Repositories:
    """Lazily-bound collection of every table repository.

    Construct once per process (or per Lambda invocation) and share. Table names are
    ``<prefix>-<table>`` where ``prefix`` defaults to ``RESOLVEAI_TABLE_PREFIX`` or
    ``resolveai-dev``.
    """

    def __init__(
        self,
        *,
        prefix: str | None = None,
        dynamodb: DynamoDBServiceResource | None = None,
    ) -> None:
        resolved_prefix = prefix or os.environ.get("RESOLVEAI_TABLE_PREFIX", DEFAULT_TABLE_PREFIX)
        resource = dynamodb if dynamodb is not None else boto3.resource("dynamodb")

        self.customers = CustomerRepository(
            resource.Table(_table_name(resolved_prefix, "customers"))
        )
        self.orders = OrderRepository(resource.Table(_table_name(resolved_prefix, "orders")))
        self.cases = CaseRepository(resource.Table(_table_name(resolved_prefix, "cases")))
        self.messages = MessageRepository(resource.Table(_table_name(resolved_prefix, "messages")))
        self.agent_events = AgentEventRepository(
            resource.Table(_table_name(resolved_prefix, "agent_events"))
        )
        self.approvals = ApprovalRepository(
            resource.Table(_table_name(resolved_prefix, "approvals"))
        )
        self.processed_events = ProcessedEventRepository(
            resource.Table(_table_name(resolved_prefix, "processed_events"))
        )
