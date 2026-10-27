"""Agent runtime configuration: environment variable first, then SSM Parameter Store.

Parameters live under ``/resolveai/dev/`` (``01-infrastructure.md`` §5); the prefix can
be overridden with ``RESOLVEAI_SSM_PREFIX``. Values are cached per process and never
logged.
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError

__all__ = ["ConfigError", "get_optional_param", "get_param"]

_DEFAULT_SSM_PREFIX = "/resolveai/dev"


class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing from env and SSM."""


@lru_cache(maxsize=16)
def _ssm_value(full_name: str) -> str:
    try:
        resp = boto3.client("ssm").get_parameter(Name=full_name, WithDecryption=True)
    except (ClientError, BotoCoreError) as exc:
        raise ConfigError(f"cannot read SSM parameter {full_name}: {exc}") from exc
    return str(resp["Parameter"]["Value"])


def get_param(name: str, env_var: str) -> str:
    """Return config ``name`` (e.g. ``bedrock/model_id``) from ``env_var`` or SSM.

    Raises:
        ConfigError: if the value is in neither the environment nor SSM.
    """
    value = os.environ.get(env_var)
    if value:
        return value
    prefix = os.environ.get("RESOLVEAI_SSM_PREFIX", _DEFAULT_SSM_PREFIX).rstrip("/")
    return _ssm_value(f"{prefix}/{name}")


def get_optional_param(name: str, env_var: str) -> str | None:
    """Like ``get_param`` but returns ``None`` when the value is not configured."""
    try:
        return get_param(name, env_var)
    except ConfigError:
        return None
