"""Tests for structured logging and PII masking."""

from __future__ import annotations

import json
import logging

from resolveai_common.logging import JsonFormatter, get_logger, mask_text


def _format(record: logging.LogRecord) -> dict:
    return json.loads(JsonFormatter().format(record))


def test_mask_text_inline_phone() -> None:
    masked = mask_text("Hubungi 081234567890 sekarang")
    assert "081234567890" not in masked
    assert "+62812****890" in masked


def test_formatter_masks_message_and_extra() -> None:
    logger = logging.getLogger("test.logging")
    record = logger.makeRecord(
        "test.logging",
        logging.INFO,
        __file__,
        1,
        "Pesan ke +6281234567890",
        None,
        None,
        extra={"case_id": "CASE-20261027-0001", "phone": "081234567890"},
    )
    payload = _format(record)
    assert payload["case_id"] == "CASE-20261027-0001"
    assert payload["phone"] == "+62812****890"
    assert "+6281234567890" not in payload["message"]
    assert payload["level"] == "INFO"


def test_get_logger_binds_case_id() -> None:
    adapter = get_logger("test.adapter", case_id="CASE-X")
    assert adapter.extra == {"case_id": "CASE-X"}


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def test_get_logger_keeps_extra_fields_and_masks_phone() -> None:
    logger = logging.getLogger("test.adapter.extra")
    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        get_logger("test.adapter.extra", case_id="CASE-X").info(
            "agent turn completed",
            extra={
                "latency_ms": 42,
                "phone": "+6281234567890",
                "case_id": "CASE-OTHER",
            },
        )
    finally:
        logger.removeHandler(handler)

    [line] = handler.lines
    payload = json.loads(line)
    assert payload["latency_ms"] == 42
    assert payload["phone"] == "+62812****890"
    assert "+6281234567890" not in line
    # Bound correlation ID wins over a per-call value.
    assert payload["case_id"] == "CASE-X"
