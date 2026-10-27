"""Result type shared by every messaging adapter.

``SendResult`` is the single return type for ``send_email``/``send_whatsapp``/
``send_sms`` (MSG-001). Adapters never raise to the caller: botocore errors are caught
and reported as ``SendResult(ok=False, error=...)`` so the agent/dispatcher can fall
back to another channel (``05-messaging.md`` §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Channel

__all__ = ["SendResult"]


@dataclass(frozen=True)
class SendResult:
    """Outcome of a single outbound send attempt.

    Attributes:
        ok: Whether the provider accepted the message.
        channel: The channel the attempt used.
        provider_message_id: Provider-assigned message id on success, else ``None``.
        error: Human-readable failure reason on error, else ``None``.
        raw: Raw provider response or error payload, for logging/debugging.
    """

    ok: bool
    channel: Channel
    provider_message_id: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
