"""Tests for phone normalization and masking."""

from __future__ import annotations

import pytest
from resolveai_common.phone import mask_phone, normalize_phone


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0812345678901", "+62812345678901"),
        ("081234567890", "+6281234567890"),
        ("6281234567890", "+6281234567890"),
        ("+6281234567890", "+6281234567890"),
        ("+62 812-3456-7890", "+6281234567890"),
        ("0812 3456 7890", "+6281234567890"),
        ("812345678", "+62812345678"),
    ],
)
def test_normalize_valid(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "abc", "+1 555 123 4567", "123", "+62123"],
)
def test_normalize_invalid_returns_none(raw: str | None) -> None:
    assert normalize_phone(raw) is None


def test_mask_valid() -> None:
    assert mask_phone("081234567890") == "+62812****890"
    assert mask_phone("+6281234567890") == "+62812****890"


def test_mask_invalid_placeholder() -> None:
    assert mask_phone(None) == "+62***"
    assert mask_phone("garbage") == "+62***"
