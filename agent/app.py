"""Bedrock AgentCore Runtime entrypoint (AG-001): parse payload, run turn, return JSON.

Run from the repo root with ``python -m agent.app`` (serves ``POST /invocations`` and
``GET /ping`` on port 8080). Vendored dependencies are set up in ``agent/__init__.py``.
"""

from __future__ import annotations

from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agent.runner import run_turn

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore invocation handler; always returns the §8 response shape."""
    return run_turn(payload)


if __name__ == "__main__":
    app.run()
