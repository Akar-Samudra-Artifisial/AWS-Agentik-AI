"""Runtime configuration: environment variable first, then SSM Parameter Store.

Parameters live under ``/resolveai/dev/`` (``01-infrastructure.md`` §5). The prefix can be
overridden with ``RESOLVEAI_SSM_PREFIX``. Values are cached per process; secrets are
never logged.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

__all__ = ["ConfigError", "get_param", "now_iso", "parse_iso", "to_iso"]

_DEFAULT_SSM_PREFIX = "/resolveai/dev"


class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing from env and SSM."""


@lru_cache(maxsize=32)
def _ssm_value(full_name: str) -> str:
    try:
        resp = boto3.client("ssm").get_parameter(Name=full_name, WithDecryption=True)
    except (ClientError, BotoCoreError) as exc:
        raise ConfigError(f"cannot read SSM parameter {full_name}: {exc}") from exc
    return str(resp["Parameter"]["Value"])


def get_param(name: str, env_var: str) -> str:
    """Return config ``name`` (e.g. ``api/key``) from ``env_var`` or SSM.

    Raises:
        ConfigError: if the value is in neither the environment nor SSM.
    """
    value = os.environ.get(env_var)
    if value:
        return value
    prefix = os.environ.get("RESOLVEAI_SSM_PREFIX", _DEFAULT_SSM_PREFIX).rstrip("/")
    return _ssm_value(f"{prefix}/{name}")


def to_iso(moment: datetime) -> str:
    """Format a datetime as ISO 8601 UTC with a ``Z`` suffix (second precision)."""
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def now_iso() -> str:
    """Current time as ISO 8601 UTC (``2026-10-28T03:00:00Z``)."""
    return to_iso(datetime.now(UTC))


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 timestamp; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
