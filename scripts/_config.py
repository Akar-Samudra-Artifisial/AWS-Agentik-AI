"""Shared helpers for the operational scripts (ingest/eval/e2e).

Configuration is resolved in this order: explicit CLI value → environment variable →
SSM Parameter Store ``/resolveai/dev/<name>`` (prefix overridable with
``RESOLVEAI_SSM_PREFIX``). Values are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

__all__ = ["REPO_ROOT", "ConfigError", "load_yaml", "resolve_config"]

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SSM_PREFIX = "/resolveai/dev"


class ConfigError(RuntimeError):
    """A required configuration value is missing from CLI, env and SSM."""


def resolve_config(
    value: str | None,
    env_var: str,
    ssm_name: str | None = None,
    *,
    ssm_client: Any | None = None,
) -> str:
    """Return ``value`` or the first configured source; raise ``ConfigError`` if none."""
    if value:
        return value
    from_env = os.environ.get(env_var, "").strip()
    if from_env:
        return from_env
    if ssm_name:
        prefix = os.environ.get("RESOLVEAI_SSM_PREFIX", _DEFAULT_SSM_PREFIX).rstrip("/")
        full_name = f"{prefix}/{ssm_name}"
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError

            client = ssm_client or boto3.client("ssm")
            try:
                resp = client.get_parameter(Name=full_name, WithDecryption=True)
            except (BotoCoreError, ClientError) as exc:
                raise ConfigError(
                    f"{env_var} tidak di-set dan SSM {full_name} tidak terbaca: {exc}"
                ) from exc
        except ImportError as exc:  # pragma: no cover - boto3 is a dev dependency
            raise ConfigError(
                f"{env_var} tidak di-set dan boto3 tidak tersedia"
            ) from exc
        return str(resp["Parameter"]["Value"])
    raise ConfigError(f"{env_var} tidak di-set (atau berikan lewat argumen)")


def load_yaml(path: Path) -> Any:
    """Parse a YAML file; raise ``ValueError`` with the path when it is invalid."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML tidak valid di {path}: {exc}") from exc
