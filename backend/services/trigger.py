"""How the API hands work to the dispatcher (``00-overview.md`` §8: API -> async dispatcher).

``LambdaAsyncTrigger`` invokes the dispatcher Lambda with ``InvocationType=Event`` so the
API answers 202 quickly. ``InlineTrigger`` runs the dispatcher in-process (local runs and
tests) with the injected ``Deps``, including its ``AgentInvoker``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

import boto3

__all__ = ["InlineTrigger", "LambdaAsyncTrigger", "Trigger", "build_default_trigger"]

Trigger = Callable[[dict[str, Any]], None]


class LambdaAsyncTrigger:
    """Fire-and-forget invoke of the dispatcher Lambda."""

    def __init__(self, function_name: str, client: Any | None = None) -> None:
        self._function_name = function_name
        self._client = client

    def __call__(self, payload: dict[str, Any]) -> None:
        if self._client is None:
            self._client = boto3.client("lambda")
        self._client.invoke(
            FunctionName=self._function_name,
            InvocationType="Event",
            Payload=json.dumps(payload).encode("utf-8"),
        )


class InlineTrigger:
    """Run the dispatcher synchronously in this process."""

    def __init__(self, deps_provider: Callable[[], Any]) -> None:
        self._deps_provider = deps_provider

    def __call__(self, payload: dict[str, Any]) -> None:
        from dispatcher.core import handle_event

        handle_event(self._deps_provider(), payload)


def build_default_trigger(deps_provider: Callable[[], Any]) -> Trigger:
    """Async Lambda invoke when ``DISPATCHER_FUNCTION_NAME`` is set, else inline."""
    function_name = os.environ.get("DISPATCHER_FUNCTION_NAME")
    if function_name:
        return LambdaAsyncTrigger(function_name)
    return InlineTrigger(deps_provider)
