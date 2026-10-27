"""Tests for the deterministic resolution-notice templates (MSG-006, PRD 05 §5).

Covers per-channel formatting, the length limits (WhatsApp <=600, SMS <=160), SMS
truncation, optional voucher placeholder, and HTML escaping in the email body.
"""

from __future__ import annotations

import pytest
from resolveai_common.messaging import templates

_BASE = {
    "case_id": "CASE-001",
    "customer_name": "Rani",
    "summary": "Pesanan Anda terlambat, kami berikan kompensasi.",
    "next_steps": "Paket tiba dalam 2 hari.",
}


# --------------------------------------------------------------------------- #
# WhatsApp
# --------------------------------------------------------------------------- #
def test_render_whatsapp_contains_all_parts() -> None:
    msg = templates.render_whatsapp(**_BASE, voucher_code="VC-10")

    assert "Halo Rani," in msg
    assert _BASE["summary"] in msg
    assert "Langkah berikutnya: Paket tiba dalam 2 hari." in msg
    assert "Kode voucher: VC-10" in msg
    assert "Kode kasus: CASE-001" in msg
    assert len(msg) <= templates.WHATSAPP_MAX_CHARS


def test_render_whatsapp_without_voucher_omits_line() -> None:
    msg = templates.render_whatsapp(**_BASE)

    assert "Kode voucher" not in msg


def test_render_whatsapp_raises_when_too_long() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        templates.render_whatsapp(
            case_id="CASE-001",
            customer_name="Rani",
            summary="x" * (templates.WHATSAPP_MAX_CHARS + 1),
            next_steps="y",
        )


# --------------------------------------------------------------------------- #
# SMS
# --------------------------------------------------------------------------- #
def test_render_sms_fits_single_segment() -> None:
    sms = templates.render_sms(**_BASE)

    assert len(sms) <= templates.SMS_MAX_CHARS
    assert "(Kasus CASE-001)" in sms


def test_render_sms_truncates_long_summary() -> None:
    sms = templates.render_sms(
        case_id="CASE-001",
        customer_name="Rani",
        summary="a" * 400,
        next_steps="n",
    )

    assert len(sms) <= templates.SMS_MAX_CHARS
    assert sms.endswith("(Kasus CASE-001)")
    assert "…" in sms


def test_render_sms_includes_voucher_when_present() -> None:
    sms = templates.render_sms(**_BASE, voucher_code="VC-10")

    assert "Voucher: VC-10." in sms
    assert len(sms) <= templates.SMS_MAX_CHARS


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #
def test_render_email_subject_format() -> None:
    assert templates.render_email_subject("CASE-001") == (
        "[ResolveAI] Kasus CASE-001 telah diselesaikan"
    )


def test_render_email_has_subject_html_text() -> None:
    content = templates.render_email(**_BASE, voucher_code="VC-10")

    assert content.subject == "[ResolveAI] Kasus CASE-001 telah diselesaikan"
    assert "CASE-001" in content.html
    assert "Voucher:</strong> VC-10" in content.html
    assert "Langkah berikutnya: Paket tiba dalam 2 hari." in content.text
    assert "Voucher: VC-10" in content.text


def test_render_email_without_voucher_omits_it() -> None:
    content = templates.render_email(**_BASE)

    assert "Voucher" not in content.html
    assert "Voucher" not in content.text


def test_render_email_escapes_html_in_values() -> None:
    content = templates.render_email(
        case_id="CASE-001",
        customer_name="<script>alert(1)</script>",
        summary="ringkasan & <b>bold</b>",
        next_steps="langkah",
    )

    assert "<script>" not in content.html
    assert "&lt;script&gt;" in content.html
    assert "&amp;" in content.html
    # Plain-text alternative is not escaped.
    assert "ringkasan & <b>bold</b>" in content.text
