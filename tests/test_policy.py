"""Tests for policy constants — values must match PRD §10 defaults."""

from __future__ import annotations

import importlib

from resolveai_common import policy


def test_default_constant_values() -> None:
    assert policy.DELAY_APOLOGY_DAYS == 1
    assert policy.DELAY_COMPENSATION_DAYS == 2
    assert policy.LOST_THRESHOLD_DAYS == 5
    assert policy.VOUCHER_MAX_IDR == 25_000
    assert policy.AUTO_REFUND_LIMIT_IDR == 100_000
    assert policy.MAX_TOOL_CALLS_PER_TURN == 8
    assert policy.MAX_OUTBOUND_PER_TURN == 5
    assert policy.CASE_REUSE_WINDOW_HOURS == 24
    assert policy.STAFF_HOURS_START == 8
    assert policy.STAFF_HOURS_END == 20


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("VOUCHER_MAX_IDR", "50000")
    reloaded = importlib.reload(policy)
    try:
        assert reloaded.VOUCHER_MAX_IDR == 50_000
    finally:
        monkeypatch.delenv("VOUCHER_MAX_IDR", raising=False)
        importlib.reload(policy)


def test_invalid_env_raises(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_REFUND_LIMIT_IDR", "not-a-number")
    try:
        import pytest

        with pytest.raises(ValueError):
            importlib.reload(policy)
    finally:
        monkeypatch.delenv("AUTO_REFUND_LIMIT_IDR", raising=False)
        importlib.reload(policy)
