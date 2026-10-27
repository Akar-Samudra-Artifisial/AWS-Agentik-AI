"""Shared constants and fakes for agent tool tests (imported by conftest and tests).

Importing this module also puts the repo root on ``sys.path`` so the top-level
``agent`` package is importable without changing the root ``tests/conftest.py``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Channel

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

PREFIX = "test"
# 10:00 WIB -> staff on duty.
NOW = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
CUSTOMER_PHONE = "+628000000001"
CUSTOMER_EMAIL = "pelanggan@example.com"


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class FakeSender:
    """Records every send; returns ok unless the channel is listed in ``failing``."""

    failing: set[Channel] = field(default_factory=set)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, channel: Channel, **kwargs: Any) -> SendResult:
        self.calls.append({"channel": channel, **kwargs})
        if channel in self.failing:
            return SendResult(ok=False, channel=channel, error="simulated failure")
        return SendResult(
            ok=True, channel=channel, provider_message_id=f"pm-{len(self.calls)}"
        )
