"""DynamoDB helpers the shared ``Repositories`` do not provide.

Kept here (not in ``packages/common``) per task scope: full-table scans for the small
demo volume (``02-backend.md`` §6), partial case updates that must not clobber a held
lock, and the conditional approval decision (BE-011).
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError
from resolveai_common.models import Approval
from resolveai_common.repository import from_dynamo

__all__ = [
    "ApprovalAlreadyDecidedError",
    "decide_approval",
    "scan_all",
    "set_case_first_inbound",
    "set_case_first_response",
    "update_case_fields",
]


class ApprovalAlreadyDecidedError(RuntimeError):
    """Raised when an approval is no longer ``pending``."""


def scan_all(table: Any) -> list[dict[str, Any]]:
    """Paginated full scan returning plain Python items (``Decimal`` -> ``int``)."""
    items: list[dict[str, Any]] = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return [from_dynamo(item) for item in items]


def update_case_fields(table: Any, case_id: str, fields: dict[str, Any]) -> None:
    """``SET`` the given attributes on a case without touching other attributes."""
    names = {f"#f{i}": key for i, key in enumerate(fields)}
    values = {f":v{i}": value for i, value in enumerate(fields.values())}
    assignments = ", ".join(f"#f{i} = :v{i}" for i in range(len(fields)))
    table.update_item(
        Key={"case_id": case_id},
        UpdateExpression=f"SET {assignments}",
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def set_case_first_inbound(table: Any, case_id: str, now: str) -> None:
    """Bump ``updated_at`` and set ``first_inbound_at`` only if it is empty."""
    table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET updated_at = :now, first_inbound_at = if_not_exists("
        "first_inbound_at, :now)",
        ExpressionAttributeValues={":now": now},
    )


def set_case_first_response(table: Any, case_id: str, now: str) -> None:
    """Set ``first_response_at`` on the first outbound message only (MSG-007)."""
    table.update_item(
        Key={"case_id": case_id},
        UpdateExpression="SET updated_at = :now, first_response_at = if_not_exists("
        "first_response_at, :now)",
        ExpressionAttributeValues={":now": now},
    )


def decide_approval(
    table: Any,
    approval_id: str,
    *,
    status: str,
    decided_at: str,
    decided_by: str,
    note: str | None,
) -> Approval:
    """Move a ``pending`` approval to ``status`` atomically (idempotent, BE-011).

    Raises:
        ApprovalAlreadyDecidedError: if the approval is not ``pending`` any more.
    """
    expression = "SET #s = :status, decided_at = :at, decided_by = :by"
    values: dict[str, Any] = {
        ":status": status,
        ":at": decided_at,
        ":by": decided_by,
        ":pending": "pending",
    }
    if note:
        expression += ", note = :note"
        values[":note"] = note
    try:
        resp = table.update_item(
            Key={"approval_id": approval_id},
            UpdateExpression=expression,
            ConditionExpression="attribute_exists(approval_id) AND #s = :pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApprovalAlreadyDecidedError(
                f"approval {approval_id} already decided"
            ) from exc
        raise
    return Approval.model_validate(from_dynamo(resp["Attributes"]))
