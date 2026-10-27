"""Lambda entrypoint for the dispatcher (SNS inbound + async invokes from ``api``)."""

from __future__ import annotations

from typing import Any

from resolveai_common.logging import configure_root_logger
from services.deps import Deps, build_default_deps

from .core import handle_event

__all__ = ["handler"]

configure_root_logger()

_deps: Deps | None = None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler; dependencies are built once per container."""
    global _deps
    if _deps is None:
        _deps = build_default_deps()
    return handle_event(_deps, event)
