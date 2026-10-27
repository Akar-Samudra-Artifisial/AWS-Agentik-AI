"""Tests for the send_test_message CLI (MSG-010).

The script lives under ``scripts/`` (not importable as a package), so it is loaded from
its file path. ``send_on_channel`` is patched so no AWS call is made: these tests cover
argument parsing, recipient validation/normalization, routing, and exit codes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Channel

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "send_test_message.py"


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("send_test_message_cli", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _ok(channel: Channel) -> SendResult:
    return SendResult(ok=True, channel=channel, provider_message_id="id-1")


def test_send_email_routes_with_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(channel: Channel, **kwargs: object) -> SendResult:
        captured.update(kwargs)
        captured["channel"] = channel
        return _ok(channel)

    monkeypatch.setattr(cli, "send_on_channel", fake)

    result = cli._send(Channel.EMAIL, "to@example.com", "halo", "Subjek")

    assert result.ok is True
    assert captured["channel"] is Channel.EMAIL
    assert captured["to_email"] == "to@example.com"
    assert captured["subject"] == "Subjek"


def test_send_email_rejects_non_email() -> None:
    with pytest.raises(ValueError, match="email address"):
        cli._send(Channel.EMAIL, "+6281234567890", "halo", "s")


def test_send_sms_normalizes_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(channel: Channel, **kwargs: object) -> SendResult:
        captured.update(kwargs)
        return _ok(channel)

    monkeypatch.setattr(cli, "send_on_channel", fake)

    cli._send(Channel.SMS, "081234567890", "halo", "s")

    assert captured["to_e164"] == "+6281234567890"


def test_send_rejects_invalid_phone() -> None:
    with pytest.raises(ValueError, match="invalid phone"):
        cli._send(Channel.WHATSAPP, "not-a-number", "halo", "s")


def test_main_success_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "send_on_channel", lambda channel, **_: _ok(channel))

    code = cli.main(["--channel", "email", "--to", "to@example.com"])

    assert code == 0


def test_main_send_failure_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "send_on_channel",
        lambda channel, **_: SendResult(ok=False, channel=channel, error="boom"),
    )

    code = cli.main(["--channel", "email", "--to", "to@example.com"])

    assert code == 1


def test_main_invalid_input_returns_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "send_on_channel", lambda channel, **_: _ok(channel))

    # invalid phone for sms -> _send raises ValueError -> exit code 2
    code = cli.main(["--channel", "sms", "--to", "bogus"])

    assert code == 2


def test_main_rejects_unknown_channel() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--channel", "pigeon", "--to", "x"])
