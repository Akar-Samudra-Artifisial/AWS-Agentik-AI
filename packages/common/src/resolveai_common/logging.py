"""Structured JSON logging for ResolveAI.

Emits one JSON object per log line with a stable schema. ``case_id`` acts as the
correlation ID and is carried through all records produced by a case-scoped logger.
Phone numbers embedded in messages or ``extra`` fields are masked automatically so
PII never reaches the logs.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

from .phone import mask_phone

__all__ = ["configure_root_logger", "get_logger", "JsonFormatter", "mask_text"]

# Matches Indonesian phone numbers appearing inline in free text.
_PHONE_IN_TEXT_RE = re.compile(r"(?<!\d)(\+?62\d{8,13}|0\d{8,12})(?!\d)")

# LogRecord attributes that are not user-provided "extra" fields.
_RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


def mask_text(text: str) -> str:
    """Mask any Indonesian phone numbers found inline in ``text``.

    Args:
        text: Free text that may contain phone numbers.

    Returns:
        The text with each detected phone number replaced by its masked form.
    """
    return _PHONE_IN_TEXT_RE.sub(lambda m: mask_phone(m.group(0)), text)


def _mask_value(value: Any) -> Any:
    """Recursively mask phone-like strings inside ``extra`` field values."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mask_value(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON with masked PII."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": mask_text(record.getMessage()),
        }

        # Phone fields get explicit masking regardless of their value format.
        extras: dict[str, Any] = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_ATTRS and not key.startswith("_")
        }
        for key, value in extras.items():
            if key in {"phone", "phone_e164", "from_e164", "to_e164"} and isinstance(value, str):
                payload[key] = mask_phone(value)
            else:
                payload[key] = _mask_value(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_root_logger(level: int = logging.INFO) -> None:
    """Install the JSON formatter on the root logger's stdout handler.

    Idempotent: calling it repeatedly replaces existing handlers so logs are not
    duplicated. Intended to be called once at process startup.

    Args:
        level: Minimum log level for the root logger.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


class _CaseLoggerAdapter(logging.LoggerAdapter):  # type: ignore[type-arg]
    """Adapter that merges per-call ``extra`` with the bound context.

    The stdlib ``LoggerAdapter.process`` replaces the caller's ``extra`` with the
    adapter's own, dropping structured fields. Bound context (``case_id``) wins over
    per-call values so the correlation ID cannot be overridden accidentally.
    """

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        kwargs["extra"] = {**(kwargs.get("extra") or {}), **(self.extra or {})}
        return msg, kwargs


def get_logger(name: str, case_id: str | None = None) -> logging.LoggerAdapter:  # type: ignore[type-arg]
    """Return a logger adapter that injects ``case_id`` into every record.

    Per-call ``extra`` fields are preserved and emitted alongside ``case_id``.

    Args:
        name: Logger name, typically ``__name__``.
        case_id: Correlation ID bound to all records from this adapter.

    Returns:
        A ``LoggerAdapter`` that adds ``case_id`` as structured context.
    """
    logger = logging.getLogger(name)
    return _CaseLoggerAdapter(logger, {"case_id": case_id})
