"""Conversation harness over the dashboard API, shared by ``e2e.py`` and ``eval_agent.py``.

A conversation is a list of steps — a customer message (``POST /api/simulate/inbound``)
or a staff approval decision (``POST /api/approvals/{id}/decision``). After each step
the harness polls ``GET /api/cases/{id}`` until the agent turn finished (a new
``model_message``/``error`` event) and finally checks an ``Expectation`` against the
case detail: tools called, status, resolution, priority, approvals, outbound replies.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

__all__ = [
    "ApiClient",
    "Conversation",
    "Expectation",
    "Outcome",
    "Step",
    "detect_language",
    "evaluate",
    "parse_conversation",
    "run_conversation",
]

TERMINAL_STATUSES = frozenset({"resolved", "escalated", "error"})
_TURN_END_EVENTS = frozenset({"model_message", "error"})

_EN_WORDS = frozenset(
    {
        "the", "you", "your", "we", "our", "is", "are", "was", "will", "order", "please",
        "sorry", "thank", "thanks", "for", "and", "with", "has", "have", "been", "delivery",
        "package",
    }
)  # fmt: skip
_ID_WORDS = frozenset(
    {
        "yang", "anda", "kami", "ini", "itu", "dan", "untuk", "dengan", "pesanan", "mohon",
        "maaf", "terima", "kasih", "akan", "sudah", "paket", "pengiriman", "silakan",
    }
)  # fmt: skip
_WORD_RE = re.compile(r"[a-zA-Z]+")


class ApiClient:
    """Minimal client for the ResolveAI API (``02-backend.md`` §5)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"x-api-key": api_key},
            timeout=timeout,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"{method} {path} gagal: HTTP {resp.status_code} {resp.text[:300]}"
            )
        return resp.json() if resp.content else {}

    def simulate_inbound(
        self, channel: str, from_e164: str, text: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/simulate/inbound",
            json={"channel": channel, "from_e164": from_e164, "text": text},
        )

    def get_case(self, case_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/cases/{case_id}")

    def decide(
        self, approval_id: str, decision: str, decided_by: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/approvals/{approval_id}/decision",
            json={"decision": decision, "decided_by": decided_by},
        )

    def demo_reset(self) -> dict[str, Any]:
        return self._request("POST", "/api/demo/reset")

    def close(self) -> None:
        self._http.close()


@dataclass(frozen=True)
class Step:
    """``customer`` text, or ``approval`` = ``approve``/``reject`` on the pending approval."""

    customer: str | None = None
    approval: str | None = None


@dataclass(frozen=True)
class Expectation:
    tools_called: tuple[str, ...] = ()
    tools_not_called: tuple[str, ...] = ()
    tools_any: tuple[str, ...] = ()
    status_in: tuple[str, ...] = ()
    resolution_type_in: tuple[str, ...] = ()
    priority_in: tuple[str, ...] = ()
    approval_status_in: tuple[str, ...] = ()
    tool_output_contains: dict[str, str] = field(default_factory=dict)
    min_outbound: int = 0
    reply_language: str | None = None
    reply_regex: tuple[str, ...] = ()


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    steps: tuple[Step, ...]
    expect: Expectation
    critical: bool = False


@dataclass
class Outcome:
    conversation_id: str
    case_id: str | None = None
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def _str_tuple(raw: Any, name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return tuple(raw)
    raise ValueError(f"{name} harus string atau daftar string")


def parse_conversation(raw: dict[str, Any]) -> Conversation:
    """Build a ``Conversation`` from a YAML/dict entry; raise ``ValueError`` if invalid."""
    if not isinstance(raw, dict) or "id" not in raw:
        raise ValueError(f"percakapan tanpa id: {raw!r}")
    conv_id = str(raw["id"])
    steps: list[Step] = []
    for item in raw.get("steps") or []:
        if not isinstance(item, dict):
            raise TypeError(f"[{conv_id}] step harus mapping: {item!r}")
        if isinstance(item.get("customer"), str) and item["customer"].strip():
            steps.append(Step(customer=item["customer"]))
        elif item.get("approval") in ("approve", "reject"):
            steps.append(Step(approval=item["approval"]))
        else:
            raise ValueError(
                f"[{conv_id}] step harus 'customer' atau 'approval': {item!r}"
            )
    if not steps or steps[0].customer is None:
        raise ValueError(f"[{conv_id}] step pertama harus pesan pelanggan")
    exp = raw.get("expect") or {}
    if not isinstance(exp, dict):
        raise TypeError(f"[{conv_id}] expect harus mapping")
    unknown = set(exp) - set(Expectation.__dataclass_fields__)
    if unknown:
        raise ValueError(f"[{conv_id}] kunci expect tidak dikenal: {sorted(unknown)}")
    contains = exp.get("tool_output_contains") or {}
    if not isinstance(contains, dict):
        raise TypeError(f"[{conv_id}] tool_output_contains harus mapping")
    language = exp.get("reply_language")
    if language not in (None, "id", "en"):
        raise ValueError(f"[{conv_id}] reply_language harus 'id' atau 'en'")
    expectation = Expectation(
        tools_called=_str_tuple(exp.get("tools_called"), "tools_called"),
        tools_not_called=_str_tuple(exp.get("tools_not_called"), "tools_not_called"),
        tools_any=_str_tuple(exp.get("tools_any"), "tools_any"),
        status_in=_str_tuple(exp.get("status_in"), "status_in"),
        resolution_type_in=_str_tuple(
            exp.get("resolution_type_in"), "resolution_type_in"
        ),
        priority_in=_str_tuple(exp.get("priority_in"), "priority_in"),
        approval_status_in=_str_tuple(
            exp.get("approval_status_in"), "approval_status_in"
        ),
        tool_output_contains={str(k): str(v) for k, v in contains.items()},
        min_outbound=int(exp.get("min_outbound", 0)),
        reply_language=language,
        reply_regex=_str_tuple(exp.get("reply_regex"), "reply_regex"),
    )
    return Conversation(
        id=conv_id,
        title=str(raw.get("title", "")),
        steps=tuple(steps),
        expect=expectation,
        critical=bool(raw.get("critical", False)),
    )


def detect_language(text: str) -> str:
    """Rough ``en``/``id`` guess by counting common function words."""
    words = [w.lower() for w in _WORD_RE.findall(text)]
    en = sum(w in _EN_WORDS for w in words)
    idn = sum(w in _ID_WORDS for w in words)
    return "en" if en > idn else "id"


def _outbound_agent_messages(detail: dict[str, Any]) -> list[dict[str, Any]]:
    msgs = [
        m
        for m in detail.get("messages", [])
        if m.get("direction") == "outbound" and m.get("author") in ("agent", "system")
    ]
    return sorted(msgs, key=lambda m: m.get("ts", ""))


def evaluate(expect: Expectation, detail: dict[str, Any]) -> list[str]:
    """Return human-readable failures of ``detail`` (``GET /cases/{id}``) vs ``expect``."""
    failures: list[str] = []
    case = detail.get("case") or {}
    events = detail.get("events") or []
    called = {
        e.get("tool") for e in events if e.get("type") == "tool_call" and e.get("tool")
    }

    missing = [t for t in expect.tools_called if t not in called]
    if missing:
        failures.append(f"tool wajib tidak dipanggil: {', '.join(missing)}")
    forbidden = [t for t in expect.tools_not_called if t in called]
    if forbidden:
        failures.append(f"tool terlarang dipanggil: {', '.join(forbidden)}")
    if expect.tools_any and not called & set(expect.tools_any):
        failures.append(f"tidak ada satu pun dari: {', '.join(expect.tools_any)}")

    for key, allowed in (
        ("status", expect.status_in),
        ("resolution_type", expect.resolution_type_in),
        ("priority", expect.priority_in),
    ):
        if allowed and case.get(key) not in allowed:
            failures.append(
                f"{key}={case.get(key)!r}, diharapkan salah satu {list(allowed)}"
            )

    if expect.approval_status_in:
        statuses = [a.get("status") for a in detail.get("approvals") or []]
        if not any(s in expect.approval_status_in for s in statuses):
            failures.append(
                f"approval status {statuses}, diharapkan salah satu "
                f"{list(expect.approval_status_in)}"
            )

    for tool, needle in expect.tool_output_contains.items():
        outputs = [
            e.get("output") or ""
            for e in events
            if e.get("type") == "tool_result" and e.get("tool") == tool
        ]
        if not any(needle in out for out in outputs):
            failures.append(f"hasil {tool} tidak memuat {needle!r}")

    outbound = _outbound_agent_messages(detail)
    if len(outbound) < expect.min_outbound:
        failures.append(f"pesan keluar {len(outbound)} < {expect.min_outbound}")
    last_body = outbound[-1].get("body", "") if outbound else ""
    if expect.reply_language and outbound:
        lang = detect_language(last_body)
        if lang != expect.reply_language:
            failures.append(
                f"bahasa balasan {lang}, diharapkan {expect.reply_language}"
            )
    elif expect.reply_language:
        failures.append("tidak ada balasan untuk dicek bahasanya")
    for pattern in expect.reply_regex:
        if not re.search(pattern, last_body):
            failures.append(f"balasan terakhir tidak cocok pola {pattern!r}")
    return failures


def _turn_marker(detail: dict[str, Any]) -> int:
    return sum(
        1 for e in detail.get("events") or [] if e.get("type") in _TURN_END_EVENTS
    )


def wait_for_turn(
    client: ApiClient,
    case_id: str,
    baseline: int,
    *,
    timeout: float,
    poll: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Poll the case until a new ``model_message``/``error`` event appears."""
    deadline = clock() + timeout
    while True:
        detail = client.get_case(case_id)
        if (
            _turn_marker(detail) > baseline
            or (detail.get("case") or {}).get("status") == "error"
        ):
            return detail
        if clock() >= deadline:
            raise TimeoutError(
                f"giliran agen {case_id} tidak selesai dalam {timeout:.0f} dtk"
            )
        sleep(poll)


def run_conversation(
    client: ApiClient,
    conv: Conversation,
    *,
    phone: str,
    channel: str,
    decided_by: str = "resolveai-script",
    turn_timeout: float = 150.0,
    poll: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Outcome:
    """Play ``conv`` against the API and evaluate its expectation; never raises."""
    outcome = Outcome(conversation_id=conv.id)
    detail: dict[str, Any] = {}
    try:
        for index, step in enumerate(conv.steps, start=1):
            if (
                outcome.case_id
                and (detail.get("case") or {}).get("status") in TERMINAL_STATUSES
            ) and step.customer is not None:
                # A closed case is not reused; later customer steps are moot.
                break
            baseline = _turn_marker(detail)
            if step.customer is not None:
                resp = client.simulate_inbound(channel, phone, step.customer)
                case_id = resp.get("case_id")
                if not case_id:
                    outcome.failures.append(f"step {index}: inbound tanpa case_id")
                    return outcome
                if outcome.case_id and case_id != outcome.case_id:
                    outcome.failures.append(
                        f"step {index}: pesan masuk ke kasus lain ({case_id})"
                    )
                    return outcome
                outcome.case_id = case_id
            else:
                pending = [
                    a
                    for a in detail.get("approvals") or []
                    if a.get("status") == "pending"
                ]
                if not pending:
                    outcome.failures.append(f"step {index}: tidak ada approval pending")
                    return outcome
                client.decide(pending[0]["approval_id"], str(step.approval), decided_by)
            assert outcome.case_id is not None
            detail = wait_for_turn(
                client,
                outcome.case_id,
                baseline,
                timeout=turn_timeout,
                poll=poll,
                sleep=sleep,
                clock=clock,
            )
    except (RuntimeError, TimeoutError, httpx.HTTPError) as exc:
        outcome.failures.append(f"{type(exc).__name__}: {exc}")
        return outcome
    outcome.failures.extend(evaluate(conv.expect, detail))
    return outcome
