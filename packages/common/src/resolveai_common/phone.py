"""Indonesian phone number normalization and masking utilities.

``normalize_phone`` converts common Indonesian input formats to E.164
(``+62...``). ``mask_phone`` produces a log-safe representation that hides the
middle digits (e.g. ``+62812****789``). Both treat untrusted input defensively.
"""

from __future__ import annotations

import re

__all__ = ["normalize_phone", "mask_phone"]

# E.164 allows up to 15 digits total. Indonesian national numbers are 9-13 digits
# after the country code; we keep the bound permissive but reject obvious garbage.
_E164_RE = re.compile(r"^\+62\d{8,13}$")


def normalize_phone(raw: str | None) -> str | None:
    """Normalize an Indonesian phone number to E.164 (``+62...``).

    Handles the common input shapes:
      - ``0812...``   -> ``+62812...`` (national trunk ``0`` replaced by ``+62``)
      - ``62812...``  -> ``+62812...``
      - ``+62812...`` -> unchanged
      - ``+628-12 34`` style separators are stripped before parsing

    Args:
        raw: User-provided phone string, possibly ``None`` or malformed.

    Returns:
        The E.164 string if the input is a recognizable Indonesian number,
        otherwise ``None``. Never raises on bad input.
    """
    if not raw:
        return None

    # Preserve a leading '+', strip every other non-digit character.
    has_plus = raw.strip().startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if has_plus:
        # Input already claimed international form; only +62 is supported here.
        candidate = "+" + digits
    elif digits.startswith("62"):
        candidate = "+" + digits
    elif digits.startswith("0"):
        candidate = "+62" + digits[1:]
    else:
        # Bare national number without trunk prefix, e.g. "812...".
        candidate = "+62" + digits

    return candidate if _E164_RE.match(candidate) else None


def mask_phone(raw: str | None) -> str:
    """Mask the middle digits of a phone number for safe logging.

    The input is normalized first; the ``+62`` prefix and the first 3 and last 3
    national digits are kept, the rest replaced with ``****``
    (e.g. ``+62812****789``). Unrecognized input returns a constant placeholder
    so PII never leaks into logs.

    Args:
        raw: Phone string in any supported format, possibly ``None``.

    Returns:
        A masked string, or ``"+62***"`` when the input is not a valid number.
    """
    normalized = normalize_phone(raw)
    if normalized is None:
        return "+62***"

    national = normalized[3:]  # digits after "+62"
    if len(national) <= 6:
        # Too short to show both head and tail; mask everything after prefix.
        return "+62****"

    return f"+62{national[:3]}****{national[-3:]}"
