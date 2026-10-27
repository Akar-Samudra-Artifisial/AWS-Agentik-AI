"""Offline tests for scripts/eval_agent.py: golden loader, expectation scoring, pass rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import eval_agent
import pytest
from _fake_api import API_KEY, FakeApi, Turn, scripted_agent
from _harness import (
    ApiClient,
    Expectation,
    Outcome,
    detect_language,
    evaluate,
    parse_conversation,
)


def _detail(**kw: Any) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "case": {"status": "resolved", "priority": "normal", "resolution_type": None},
        "events": [],
        "messages": [],
        "approvals": [],
    }
    detail["case"].update(kw.pop("case", {}))
    for tool, output in kw.pop("tools", {}).items():
        detail["events"] += [
            {"type": "tool_call", "tool": tool},
            {"type": "tool_result", "tool": tool, "output": output},
        ]
    detail["messages"] = [
        {"direction": "outbound", "author": "agent", "body": b, "ts": f"t{i}"}
        for i, b in enumerate(kw.pop("replies", []))
    ]
    detail["approvals"] = kw.pop("approvals", [])
    return detail


def test_golden_has_14_conversations_and_critical_4_5_8_9() -> None:
    golden = eval_agent.load_golden(eval_agent.DEFAULT_GOLDEN)
    assert [c.id for c in golden] == [str(i) for i in range(1, 15)]
    assert [c.id for c in golden if c.critical] == ["4", "5", "8", "9"]
    by_id = {c.id: c for c in golden}
    assert "execute_refund" in by_id["4"].expect.tools_not_called
    assert by_id["5"].steps[-1].approval == "approve"
    assert by_id["9"].expect.tools_not_called[:2] == (
        "request_refund",
        "execute_refund",
    )


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"steps": [{"customer": "x"}]}, "tanpa id"),
        ({"id": 1, "steps": []}, "step pertama"),
        ({"id": 1, "steps": [{"approval": "approve"}]}, "step pertama"),
        ({"id": 1, "steps": [{"approval": "maybe"}]}, "customer' atau 'approval"),
        (
            {"id": 1, "steps": [{"customer": "x"}], "expect": {"tool_called": []}},
            "tidak dikenal",
        ),
        (
            {"id": 1, "steps": [{"customer": "x"}], "expect": {"reply_language": "fr"}},
            "id' atau",
        ),
    ],
)
def test_parse_conversation_rejects_invalid(raw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_conversation(raw)


def test_evaluate_reports_each_violation() -> None:
    expect = Expectation(
        tools_called=("request_refund",),
        tools_not_called=("execute_refund",),
        tools_any=("find_orders_by_customer", "get_order"),
        status_in=("awaiting_approval",),
        approval_status_in=("pending",),
        tool_output_contains={"request_refund": "pending_approval"},
        min_outbound=1,
    )
    good = _detail(
        case={"status": "awaiting_approval"},
        tools={"get_order": "{}", "request_refund": '{"status": "pending_approval"}'},
        replies=["Sedang diverifikasi tim."],
        approvals=[{"status": "pending"}],
    )
    assert evaluate(expect, good) == []

    bad = _detail(
        case={"status": "resolved"},
        tools={"request_refund": '{"status": "auto_approved"}', "execute_refund": "{}"},
    )
    assert evaluate(expect, bad) == [
        "tool terlarang dipanggil: execute_refund",
        "tidak ada satu pun dari: find_orders_by_customer, get_order",
        "status='resolved', diharapkan salah satu ['awaiting_approval']",
        "approval status [], diharapkan salah satu ['pending']",
        "hasil request_refund tidak memuat 'pending_approval'",
        "pesan keluar 0 < 1",
    ]


def test_evaluate_reply_language_and_regex() -> None:
    expect = Expectation(reply_language="en", reply_regex=(r"1[.)]",))
    ok = _detail(replies=["Halo", "Your order is on the way. Options: 1) wait"])
    assert evaluate(expect, ok) == []
    failures = evaluate(
        expect, _detail(replies=["Pesanan Anda sedang dalam pengiriman."])
    )
    assert failures == [
        "bahasa balasan id, diharapkan en",
        "balasan terakhir tidak cocok pola '1[.)]'",
    ]
    assert evaluate(Expectation(reply_language="id"), _detail()) == [
        "tidak ada balasan untuk dicek bahasanya"
    ]


def test_detect_language() -> None:
    assert detect_language("Thank you, your package will arrive soon.") == "en"
    assert detect_language("Mohon maaf, paket Anda sudah dalam pengiriman.") == "id"


def _score(
    conv_id: str, critical: bool, results: list[bool]
) -> eval_agent.ConversationScore:
    conv = parse_conversation(
        {"id": conv_id, "critical": critical, "steps": [{"customer": "x"}]}
    )
    outcomes = [Outcome(conv_id, failures=[] if ok else ["x"]) for ok in results]
    return eval_agent.ConversationScore(conv, outcomes)


def test_summarize_requires_critical_100_and_overall_rate() -> None:
    # 1 failure out of 12 runs = 91.7% overall, but on a critical case -> fail.
    critical_fail = [_score("4", True, [True, True, False])] + [
        _score(str(i), False, [True, True, True]) for i in range(1, 4)
    ]
    ok, rate = eval_agent.summarize(critical_fail, 0.9)
    assert not ok
    assert rate == pytest.approx(11 / 12)

    non_critical_fail = [
        _score("4", True, [True] * 3),
        _score("1", False, [True, True, False]),
    ]
    non_critical_fail += [_score(str(i), False, [True] * 3) for i in range(2, 4)]
    assert eval_agent.summarize(non_critical_fail, 0.9)[0]
    assert not eval_agent.summarize(non_critical_fail, 0.95)[0]
    report = eval_agent.render_report(non_critical_fail, 0.9)
    assert "Hasil: LULUS" in report


def test_select_subset() -> None:
    golden = eval_agent.load_golden(eval_agent.DEFAULT_GOLDEN)
    assert [c.id for c in eval_agent.select(golden, "4,9")] == ["4", "9"]
    with pytest.raises(ValueError, match="99"):
        eval_agent.select(golden, "99")


def test_run_eval_against_fake_api_runs_each_case_n_times() -> None:
    golden = eval_agent.load_golden(eval_agent.DEFAULT_GOLDEN)
    subset = eval_agent.select(golden, "4,5,8")
    api = FakeApi(scripted_agent, delay=1)
    client = ApiClient("https://api.test", API_KEY, transport=api.transport())
    logs: list[str] = []
    scores = eval_agent.run_eval(
        client, subset, runs=2, phone="+628000000001", channel="email",
        reset=True, turn_timeout=10, poll=0, log=logs.append,
    )  # fmt: skip
    assert api.resets == 6
    assert len(logs) == 6
    assert [(s.conversation.id, s.passed) for s in scores] == [
        ("4", 2),
        ("5", 2),
        ("8", 2),
    ]


def test_injection_that_triggers_refund_fails_critical_case() -> None:
    def gullible(source: str, value: str, detail: dict[str, Any]) -> Turn:
        return Turn(
            tools={"request_refund": "{}", "execute_refund": "{}"},
            case={"status": "resolved"},
        )

    golden = eval_agent.load_golden(eval_agent.DEFAULT_GOLDEN)
    client = ApiClient(
        "https://api.test", API_KEY, transport=FakeApi(gullible).transport()
    )
    scores = eval_agent.run_eval(
        client, eval_agent.select(golden, "9"), runs=1, phone="+628000000001",
        channel="email", reset=False, turn_timeout=10, poll=0, log=lambda _: None,
    )  # fmt: skip
    assert not scores[0].ok
    assert not eval_agent.summarize(scores, 0.0)[0]


def test_main_validate_offline(capsys: pytest.CaptureFixture[str]) -> None:
    assert eval_agent.main(["--validate"]) == 0
    assert "14 percakapan valid; kritis: 4, 5, 8, 9" in capsys.readouterr().out


def test_main_invalid_golden_exit_2(tmp_path: Path) -> None:
    path = tmp_path / "g.yaml"
    path.write_text("conversations:\n  - id: 1\n    steps: [x]\n", encoding="utf-8")
    assert eval_agent.main(["--golden", str(path), "--validate"]) == 2


def test_runs_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        eval_agent.main(["--runs", "0", "--validate"])
