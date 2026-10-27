"""Lambda fallback (AG-012): the same turn logic as the AgentCore entrypoint.

Handler: ``agent.lambda_handler.handler``. Accepts the §8 payload directly
(``lambda:Invoke``) or as a JSON ``body`` string (function URL / API Gateway proxy) and
returns the §8 response dict.
"""

from __future__ import annotations

import json
from typing import Any

from agent.runner import run_turn


def _payload(event: Any) -> Any:
    if isinstance(event, dict) and isinstance(event.get("body"), str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            return None
    return event


def handler(event: Any, context: Any) -> dict[str, Any]:
    """Lambda entry point; invalid input yields ``error`` instead of an exception."""
    return run_turn(_payload(event))
