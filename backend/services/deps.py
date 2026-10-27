"""Dependency container shared by the dispatcher and the API.

Everything with a side effect (DynamoDB, agent runtime, outbound messaging) is held
here so tests can inject moto-backed resources and stubs. Production defaults are real
AWS clients; there is no fake sender outside ``tests/``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import boto3
from resolveai_common.messaging.dispatch import send_with_fallback
from resolveai_common.messaging.types import SendResult
from resolveai_common.repository import Repositories

from .agent_client import AgentCoreClient, AgentInvoker

__all__ = ["Deps", "Sender", "build_default_deps"]

# Same signature as ``resolveai_common.messaging.dispatch.send_with_fallback``.
Sender = Callable[..., list[SendResult]]


@dataclass
class Deps:
    """Side-effecting collaborators for one process."""

    dynamodb: Any
    repos: Repositories
    invoker: AgentInvoker
    sender: Sender

    def table(self, name: str) -> Any:
        """Raw DynamoDB ``Table`` behind ``repos.<name>`` (e.g. ``"cases"``)."""
        return self.dynamodb.Table(getattr(self.repos, name).table_name)


def build_default_deps() -> Deps:
    """Production dependencies: real DynamoDB, AgentCore Runtime and AWS messaging."""
    dynamodb = boto3.resource("dynamodb")
    return Deps(
        dynamodb=dynamodb,
        repos=Repositories(dynamodb=dynamodb),
        invoker=AgentCoreClient(),
        sender=send_with_fallback,
    )
