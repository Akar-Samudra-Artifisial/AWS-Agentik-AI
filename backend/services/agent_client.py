"""AgentCore Runtime client (BE-008).

``AgentInvoker`` is the injectable seam: the dispatcher depends on the protocol, the
runtime uses ``AgentCoreClient`` (boto3 ``bedrock-agentcore`` ``invoke_agent_runtime``,
confirmed in the installed botocore: required ``agentRuntimeArn`` + ``payload``; the
``response`` output member is a streaming blob). Tests inject a stub.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import boto3
from botocore.config import Config

from .config import get_param

__all__ = [
    "SESSION_ID_MIN_LEN",
    "AgentCoreClient",
    "AgentInvocationError",
    "AgentInvoker",
    "session_id_for_case",
]

# AgentCore requires runtimeSessionId of at least 33 characters.
SESSION_ID_MIN_LEN = 33
_CLIENT_READ_TIMEOUT_S = 120


class AgentInvocationError(RuntimeError):
    """Raised when the agent runtime cannot be invoked or returns an unusable response."""


class AgentInvoker(Protocol):
    """Invoke the agent with the ``02-backend.md`` §8 payload and return its response."""

    def invoke(self, payload: dict[str, Any], session_id: str) -> dict[str, Any]: ...


def session_id_for_case(case_id: str) -> str:
    """Stable per-case runtime session id, padded to >= 33 characters."""
    return f"case-{case_id}-".ljust(SESSION_ID_MIN_LEN, "0")


def _decode_response(body: bytes, content_type: str) -> dict[str, Any]:
    text = body.decode("utf-8").strip()
    if content_type.startswith("text/event-stream"):
        # Streaming entrypoints emit "data: <json>" lines; the last one is the result.
        data_lines = [
            ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")
        ]
        text = data_lines[-1] if data_lines else ""
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentInvocationError(f"agent response is not JSON: {exc}") from exc
    if isinstance(decoded, str):
        # BedrockAgentCoreApp may JSON-encode an already serialized string.
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise AgentInvocationError("agent response is not a JSON object") from exc
    if not isinstance(decoded, dict):
        raise AgentInvocationError("agent response is not a JSON object")
    return decoded


class AgentCoreClient:
    """``AgentInvoker`` backed by Bedrock AgentCore Runtime."""

    def __init__(
        self, runtime_arn: str | None = None, client: Any | None = None
    ) -> None:
        self._runtime_arn = runtime_arn
        self._client = client

    @property
    def runtime_arn(self) -> str:
        if self._runtime_arn is None:
            self._runtime_arn = get_param("agent/runtime_arn", "AGENT_RUNTIME_ARN")
        return self._runtime_arn

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "bedrock-agentcore",
                config=Config(
                    read_timeout=_CLIENT_READ_TIMEOUT_S,
                    connect_timeout=10,
                    retries={"max_attempts": 1},
                ),
            )
        return self._client

    def invoke(self, payload: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Invoke the runtime and return the decoded JSON response.

        Raises:
            AgentInvocationError: on transport/service errors or a non-JSON response.
        """
        if len(session_id) < SESSION_ID_MIN_LEN:
            raise AgentInvocationError(
                f"runtimeSessionId must be >= {SESSION_ID_MIN_LEN} chars"
            )
        try:
            resp = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                runtimeSessionId=session_id,
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            )
            body = resp["response"].read()
        except AgentInvocationError:
            raise
        except Exception as exc:  # botocore errors, timeouts, missing config
            raise AgentInvocationError(f"invoke_agent_runtime failed: {exc}") from exc
        return _decode_response(body, str(resp.get("contentType", "application/json")))
