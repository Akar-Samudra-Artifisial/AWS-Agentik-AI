"""Tests for channel selection and the fallback chain (MSG-005).

``send_on_channel`` / ``send_with_fallback`` are tested with the adapters replaced by
fakes (via monkeypatch on the names imported into ``dispatch``), so these tests cover
routing and fallback logic only — the adapters themselves are covered in
``test_messaging_adapters.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from resolveai_common.messaging import dispatch
from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Channel


def _ok(channel: Channel, message_id: str = "ok-id") -> SendResult:
    return SendResult(ok=True, channel=channel, provider_message_id=message_id)


def _fail(channel: Channel, error: str = "boom") -> SendResult:
    return SendResult(ok=False, channel=channel, error=error)


def _record_calls(
    monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, tuple[object, ...]]]
) -> Callable[[str, SendResult], None]:
    """Patch each adapter in ``dispatch`` with a fake that records its positional args."""

    def install(name: str, result: SendResult) -> None:
        def fake(*args: object) -> SendResult:
            calls.append((name, args))
            return result

        monkeypatch.setattr(dispatch, name, fake)

    return install


# --------------------------------------------------------------------------- #
# send_on_channel routing
# --------------------------------------------------------------------------- #
def test_send_on_channel_whatsapp_routes_to_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    _record_calls(monkeypatch, calls)("send_whatsapp", _ok(Channel.WHATSAPP, "wa"))

    result = dispatch.send_on_channel(Channel.WHATSAPP, text="halo", to_e164="+628")

    assert result.provider_message_id == "wa"
    assert calls == [("send_whatsapp", ("+628", "halo"))]


def test_send_on_channel_sms_routes_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    _record_calls(monkeypatch, calls)("send_sms", _ok(Channel.SMS, "sms"))

    result = dispatch.send_on_channel(Channel.SMS, text="halo", to_e164="+628")

    assert result.provider_message_id == "sms"
    assert calls == [("send_sms", ("+628", "halo"))]


def test_send_on_channel_email_defaults_subject_and_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    _record_calls(monkeypatch, calls)("send_email", _ok(Channel.EMAIL, "email"))

    result = dispatch.send_on_channel(Channel.EMAIL, text="halo", to_email="to@x.id")

    assert result.provider_message_id == "email"
    (name, args) = calls[0]
    assert name == "send_email"
    # (to, subject, html, text) with defaults derived from text.
    assert args == ("to@x.id", "[ResolveAI] Notifikasi", "<p>halo</p>", "halo")


def test_send_on_channel_whatsapp_missing_recipient_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    _record_calls(monkeypatch, calls)("send_whatsapp", _ok(Channel.WHATSAPP))

    result = dispatch.send_on_channel(Channel.WHATSAPP, text="halo")

    assert result.ok is False
    assert "missing to_e164" in (result.error or "")
    assert calls == []  # adapter never called


def test_send_on_channel_email_missing_recipient_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    _record_calls(monkeypatch, calls)("send_email", _ok(Channel.EMAIL))

    result = dispatch.send_on_channel(Channel.EMAIL, text="halo")

    assert result.ok is False
    assert "missing to_email" in (result.error or "")
    assert calls == []


# --------------------------------------------------------------------------- #
# send_with_fallback chain
# --------------------------------------------------------------------------- #
def test_fallback_stops_on_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    install = _record_calls(monkeypatch, calls)
    install("send_whatsapp", _ok(Channel.WHATSAPP, "wa"))
    install("send_sms", _ok(Channel.SMS, "sms"))
    install("send_email", _ok(Channel.EMAIL, "email"))

    attempts = dispatch.send_with_fallback(
        text="halo", to_e164="+628", to_email="to@x.id"
    )

    assert len(attempts) == 1
    assert attempts[-1].channel is Channel.WHATSAPP
    assert attempts[-1].ok is True
    assert [name for name, _ in calls] == ["send_whatsapp"]


def test_fallback_advances_past_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    install = _record_calls(monkeypatch, [])
    install("send_whatsapp", _fail(Channel.WHATSAPP))
    install("send_sms", _fail(Channel.SMS))
    install("send_email", _ok(Channel.EMAIL, "email"))

    attempts = dispatch.send_with_fallback(
        text="halo", to_e164="+628", to_email="to@x.id"
    )

    assert [a.channel for a in attempts] == [
        Channel.WHATSAPP,
        Channel.SMS,
        Channel.EMAIL,
    ]
    assert attempts[-1].ok is True


def test_fallback_skips_channels_without_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    install = _record_calls(monkeypatch, calls)
    install("send_whatsapp", _ok(Channel.WHATSAPP))
    install("send_sms", _ok(Channel.SMS))
    install("send_email", _ok(Channel.EMAIL, "email"))

    # Only an email recipient: WhatsApp and SMS are skipped, not recorded as attempts.
    attempts = dispatch.send_with_fallback(text="halo", to_email="to@x.id")

    assert [a.channel for a in attempts] == [Channel.EMAIL]
    assert [name for name, _ in calls] == ["send_email"]


def test_fallback_all_fail_returns_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install = _record_calls(monkeypatch, [])
    install("send_whatsapp", _fail(Channel.WHATSAPP))
    install("send_sms", _fail(Channel.SMS))
    install("send_email", _fail(Channel.EMAIL))

    attempts = dispatch.send_with_fallback(
        text="halo", to_e164="+628", to_email="to@x.id"
    )

    assert len(attempts) == 3
    assert all(a.ok is False for a in attempts)


def test_fallback_honours_custom_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    install = _record_calls(monkeypatch, calls)
    install("send_whatsapp", _ok(Channel.WHATSAPP))
    install("send_sms", _ok(Channel.SMS, "sms"))
    install("send_email", _ok(Channel.EMAIL))

    attempts = dispatch.send_with_fallback(
        text="halo",
        to_e164="+628",
        to_email="to@x.id",
        order=(Channel.SMS, Channel.EMAIL, Channel.WHATSAPP),
    )

    assert attempts[-1].channel is Channel.SMS
    assert [name for name, _ in calls] == ["send_sms"]
