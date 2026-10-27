"""Execution context binding every agent tool to a single case (``03-agent.md`` §6).

A ``ToolContext`` is created once per agent turn from the invocation payload's
``case_id``. Tools read the case, customer and recipients exclusively through it, so no
tool ever accepts a recipient or case id from the model. It also carries the per-turn
budgets (``MAX_TOOL_CALLS_PER_TURN`` / ``MAX_OUTBOUND_PER_TURN``) and the injectable
side-effect ports (message sender, policy retriever, clock) used by tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import boto3
from resolveai_common.messaging import dispatch
from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Channel
from resolveai_common.repository import Repositories

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

__all__ = ["MessageSender", "PolicyRetriever", "ToolContext", "to_iso", "utc_now"]


class MessageSender(Protocol):
    """Port matching ``dispatch.send_on_channel``; the recipient comes from the case."""

    def __call__(
        self,
        channel: Channel,
        *,
        text: str,
        to_e164: str | None = None,
        to_email: str | None = None,
        subject: str | None = None,
        html: str | None = None,
    ) -> SendResult: ...


class PolicyRetriever(Protocol):
    """Knowledge-base retrieval port: returns ``[{text, source, score}]`` (top ``top_k``)."""

    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime) -> str:
    """Format an aware datetime as ISO 8601 UTC with microseconds (sortable SK component)."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _default_sender(channel: Channel, **kwargs: Any) -> SendResult:
    # Resolved at call time so the real AWS adapters are always used at runtime.
    return dispatch.send_on_channel(channel, **kwargs)


@dataclass
class ToolContext:
    """Per-turn state shared by all tools of one agent invocation."""

    case_id: str
    repos: Repositories
    dynamodb: DynamoDBServiceResource
    sender: MessageSender = _default_sender
    policy_retriever: PolicyRetriever | None = None
    clock: Callable[[], datetime] = utc_now
    tool_calls: int = 0
    outbound: int = 0
    auto_escalated: bool = False
    _seq: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        case_id: str,
        *,
        dynamodb: DynamoDBServiceResource | None = None,
        prefix: str | None = None,
        **kwargs: Any,
    ) -> ToolContext:
        """Build a context with repositories bound to ``dynamodb`` (default: boto3)."""
        resource = dynamodb if dynamodb is not None else boto3.resource("dynamodb")
        repos = Repositories(prefix=prefix, dynamodb=resource)
        return cls(case_id=case_id, repos=repos, dynamodb=resource, **kwargs)

    def now(self) -> datetime:
        return self.clock()

    def now_iso(self) -> str:
        return to_iso(self.clock())

    def next_seq(self) -> int:
        seq = self._seq
        self._seq += 1
        return seq

    def table(self, repo: Any) -> Table:
        """Raw table handle for conditional updates the repositories do not expose."""
        return self.dynamodb.Table(repo.table_name)
