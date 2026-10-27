"""Offline tests for scripts/e2e.py and the API harness, against an in-memory fake API."""

from __future__ import annotations

from typing import Any

import e2e
import pytest
from _fake_api import API_KEY, FakeApi, Turn, scripted_agent
from _harness import ApiClient


def _client(api: FakeApi, key: str = API_KEY) -> ApiClient:
    return ApiClient("https://api.test/", key, transport=api.transport())


def _run(api: FakeApi, **kw: Any) -> list[tuple[Any, float]]:
    kw.setdefault("reset", True)
    return e2e.run_scenarios(
        _client(api),
        e2e.SCENARIOS,
        phone="+628000000001",
        channel="whatsapp",
        turn_timeout=60,
        poll=0,
        sleep=lambda _: None,
        **kw,
    )


def test_all_scenarios_pass_with_well_behaved_agent() -> None:
    api = FakeApi(scripted_agent, delay=2)
    results = _run(api)
    assert [(o.conversation_id, o.failures) for o, _ in results] == [
        ("A", []), ("B-approve", []), ("B-reject", []), ("C", []),
    ]  # fmt: skip
    assert api.resets == 4
    assert all(r.headers["x-api-key"] == API_KEY for r in api.requests)
    report = e2e.render_report(results)
    assert "E2E: 4/4 skenario lulus" in report


def test_execute_refund_without_approval_fails_b_reject() -> None:
    def leaky(source: str, value: str, detail: dict[str, Any]) -> Turn:
        turn = scripted_agent(source, value, detail)
        if source == "approval" and value == "reject":
            turn.tools["execute_refund"] = "{}"
        return turn

    results = {o.conversation_id: o for o, _ in _run(FakeApi(leaky))}
    assert results["B-approve"].passed
    assert results["B-reject"].failures == ["tool terlarang dipanggil: execute_refund"]


def test_wrong_status_and_priority_reported() -> None:
    def weak(source: str, value: str, detail: dict[str, Any]) -> Turn:
        if "ORD-1003" in value:
            return Turn(tools={"escalate_to_human": "{}"}, case={"status": "escalated"})
        return scripted_agent(source, value, detail)

    [(outcome, _)] = e2e.run_scenarios(
        _client(FakeApi(weak)), e2e.select("C"), phone="+628000000001", channel="sms",
        reset=False, turn_timeout=5, poll=0, sleep=lambda _: None,
    )  # fmt: skip
    assert outcome.failures == ["priority='normal', diharapkan salah satu ['high']"]


def test_turn_timeout_is_a_failure() -> None:
    api = FakeApi(scripted_agent, delay=10_000)
    ticks = iter(range(0, 10_000, 30))
    [(outcome, _)] = e2e.run_scenarios(
        _client(api), e2e.select("C"), phone="+628000000001", channel="sms",
        reset=False, turn_timeout=60, poll=0, sleep=lambda _: None, clock=lambda: next(ticks),
    )  # fmt: skip
    assert not outcome.passed
    assert outcome.failures[0].startswith("TimeoutError")


def test_reset_failure_is_reported_per_scenario() -> None:
    results = _run(FakeApi(scripted_agent, reset_status=404))
    assert all(o.failures[0].startswith("demo reset gagal") for o, _ in results)


def test_bad_api_key_fails_cleanly() -> None:
    [(outcome, _)] = e2e.run_scenarios(
        _client(FakeApi(scripted_agent), key="salah"), e2e.select("A"), phone="+628000000001",
        channel="sms", reset=False, turn_timeout=5, poll=0, sleep=lambda _: None,
    )  # fmt: skip
    assert "HTTP 401" in outcome.failures[0]


def test_select_rejects_unknown() -> None:
    assert [s.id for s in e2e.select("A, C")] == ["A", "C"]
    with pytest.raises(ValueError, match="Z"):
        e2e.select("Z")


def test_main_end_to_end_with_fake_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    api = FakeApi(scripted_agent, delay=0)
    monkeypatch.setenv("RESOLVEAI_API_URL", "https://api.test")
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("DEMO_PHONE_E164", "+628000000001")
    monkeypatch.setattr(
        e2e,
        "ApiClient",
        lambda url, key: ApiClient(url, key, transport=api.transport()),
    )
    out = tmp_path / "e2e.md"
    assert e2e.main(["--reset", "--poll", "0", "--output", str(out)]) == 0
    assert "4/4" in capsys.readouterr().out
    assert out.exists()


def test_main_missing_config_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RESOLVEAI_API_URL", raising=False)
    assert e2e.main([]) == 2
