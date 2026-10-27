"""Single source of truth for ResolveAI business policy constants.

Values default to the figures defined in `docs/prd/00-overview.md` §10 and may be
overridden at runtime via environment variables so the same code works across dev,
test, and deployed environments. RAG policy documents (``rag/policies/``) must mirror
these numbers.

All monetary values are integer rupiah (``*_idr``).
"""

from __future__ import annotations

import os

__all__ = [
    "DELAY_APOLOGY_DAYS",
    "DELAY_COMPENSATION_DAYS",
    "LOST_THRESHOLD_DAYS",
    "VOUCHER_MAX_IDR",
    "AUTO_REFUND_LIMIT_IDR",
    "MAX_TOOL_CALLS_PER_TURN",
    "MAX_OUTBOUND_PER_TURN",
    "CASE_REUSE_WINDOW_HOURS",
    "STAFF_TIMEZONE",
    "STAFF_HOURS_START",
    "STAFF_HOURS_END",
]


def _env_int(name: str, default: int) -> int:
    """Read a non-negative integer from the environment, falling back to ``default``.

    Raises:
        ValueError: if the environment variable is set but is not a valid integer.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"env {name} must be an integer, got {raw!r}") from exc


# Days the ETA may be exceeded before an apology is offered.
DELAY_APOLOGY_DAYS: int = _env_int("DELAY_APOLOGY_DAYS", 1)

# Days the ETA may be exceeded before compensation (voucher) is offered.
DELAY_COMPENSATION_DAYS: int = _env_int("DELAY_COMPENSATION_DAYS", 2)

# Days without a tracking scan before a package is treated as lost.
LOST_THRESHOLD_DAYS: int = _env_int("LOST_THRESHOLD_DAYS", 5)

# Maximum voucher value the agent may issue automatically.
VOUCHER_MAX_IDR: int = _env_int("VOUCHER_MAX_IDR", 25_000)

# Refunds at or below this amount may be auto-approved; above requires staff approval.
AUTO_REFUND_LIMIT_IDR: int = _env_int("AUTO_REFUND_LIMIT_IDR", 100_000)

# Hard caps enforced in tool code to bound a single agent turn.
MAX_TOOL_CALLS_PER_TURN: int = _env_int("MAX_TOOL_CALLS_PER_TURN", 8)
MAX_OUTBOUND_PER_TURN: int = _env_int("MAX_OUTBOUND_PER_TURN", 5)

# Reuse an existing non-terminal case for the same customer within this window.
CASE_REUSE_WINDOW_HOURS: int = _env_int("CASE_REUSE_WINDOW_HOURS", 24)

# Staff operating hours (WIB, i.e. UTC+7), 08:00-20:00.
STAFF_TIMEZONE: str = os.environ.get("STAFF_TIMEZONE", "Asia/Jakarta")
STAFF_HOURS_START: int = _env_int("STAFF_HOURS_START", 8)
STAFF_HOURS_END: int = _env_int("STAFF_HOURS_END", 20)
