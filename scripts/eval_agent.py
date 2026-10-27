#!/usr/bin/env python3
"""Agent eval: the 14 golden conversations of ``03-agent.md`` §9 (AG-007).

Each conversation in ``agent/eval/golden.yaml`` is played ``--runs`` times against the
deployed stack through the API (real dispatcher → AgentCore → Bedrock): customer turns
via ``POST /api/simulate/inbound``, staff decisions via ``POST /api/approvals/{id}/
decision``. Before every run ``POST /api/demo/reset`` restores the seed data (disable
with ``--no-reset``; then reset manually, because orders are mutated and an open case
for the demo customer would be reused). Pass criteria: every ``critical`` conversation
passes 100% of runs and the overall pass rate is ≥ ``--min-rate`` (0.9).

Real messages are sent to the demo contact on ``--channel`` (default ``email``).

Configuration (argument → env → SSM ``/resolveai/dev/...``):
    --api-url  RESOLVEAI_API_URL   (CDK output ``api-url``)
    --api-key  API_KEY             api/key
    --phone    DEMO_PHONE_E164     demo/phone_e164

Examples:
    python scripts/eval_agent.py --runs 3 --output docs/evidence/eval_agent.md
    python scripts/eval_agent.py --cases 4,5,8,9 --runs 1
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from _config import REPO_ROOT, ConfigError, load_yaml, resolve_config
from _harness import (
    ApiClient,
    Conversation,
    Outcome,
    parse_conversation,
    run_conversation,
)

__all__ = ["ConversationScore", "load_golden", "main", "render_report", "summarize"]

DEFAULT_GOLDEN = REPO_ROOT / "agent" / "eval" / "golden.yaml"


@dataclass
class ConversationScore:
    conversation: Conversation
    outcomes: list[Outcome] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(o.passed for o in self.outcomes)

    @property
    def ok(self) -> bool:
        """Critical conversations must pass every run."""
        if self.conversation.critical:
            return bool(self.outcomes) and self.passed == len(self.outcomes)
        return True


def load_golden(path: Path) -> list[Conversation]:
    data = load_yaml(path)
    items = data.get("conversations") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError(f"{path}: kunci 'conversations' kosong atau tidak ada")
    conversations = [parse_conversation(item) for item in items]
    ids = [c.id for c in conversations]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: id percakapan duplikat")
    return conversations


def select(
    conversations: Sequence[Conversation], cases: str | None
) -> list[Conversation]:
    if not cases:
        return list(conversations)
    wanted = [c.strip() for c in cases.split(",") if c.strip()]
    known = {c.id for c in conversations}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise ValueError(f"id percakapan tidak dikenal: {', '.join(unknown)}")
    return [c for c in conversations if c.id in wanted]


def summarize(
    scores: Sequence[ConversationScore], min_rate: float
) -> tuple[bool, float]:
    """Return ``(passed, overall_rate)`` for the whole eval."""
    total = sum(len(s.outcomes) for s in scores)
    passed = sum(s.passed for s in scores)
    rate = passed / total if total else 0.0
    return all(s.ok for s in scores) and rate >= min_rate, rate


def render_report(scores: Sequence[ConversationScore], min_rate: float) -> str:
    rows = [
        "# Eval agen — percakapan emas",
        "",
        "| # | Kritis | Lulus | Situasi | Kegagalan pertama |",
        "|---|---|---|---|---|",
    ]
    for s in scores:
        first = next((o.failures[0] for o in s.outcomes if o.failures), "")
        rows.append(
            f"| {s.conversation.id} | {'ya' if s.conversation.critical else ''} | "
            f"{s.passed}/{len(s.outcomes)} | {s.conversation.title} | "
            f"{first.replace('|', '/')} |"
        )
    ok, rate = summarize(scores, min_rate)
    rows += [
        "",
        f"Tingkat lulus: {rate:.1%} (ambang {min_rate:.0%}); kasus kritis wajib 100%.",
        f"Hasil: {'LULUS' if ok else 'GAGAL'}",
    ]
    return "\n".join(rows)


def run_eval(
    client: ApiClient,
    conversations: Sequence[Conversation],
    *,
    runs: int,
    phone: str,
    channel: str,
    reset: bool,
    turn_timeout: float,
    poll: float,
    log: Callable[[str], None] = print,
) -> list[ConversationScore]:
    scores: list[ConversationScore] = []
    for conv in conversations:
        score = ConversationScore(conv)
        for run in range(1, runs + 1):
            if reset:
                client.demo_reset()
            started = time.monotonic()
            outcome = run_conversation(
                client,
                conv,
                phone=phone,
                channel=channel,
                decided_by="eval-agent",
                turn_timeout=turn_timeout,
                poll=poll,
            )
            score.outcomes.append(outcome)
            verdict = (
                "LULUS" if outcome.passed else "GAGAL: " + "; ".join(outcome.failures)
            )
            log(
                f"[{conv.id} run {run}/{runs}] {outcome.case_id or '-'} "
                f"{time.monotonic() - started:.0f}s {verdict}"
            )
        scores.append(score)
    return scores


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Eval agen dengan percakapan emas (via API)."
    )
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument(
        "--runs", type=int, default=3, help="jumlah ulangan per kasus (3)"
    )
    parser.add_argument("--cases", help="subset id, mis. 4,5,8,9")
    parser.add_argument("--api-url", help="base URL API (env RESOLVEAI_API_URL)")
    parser.add_argument("--api-key", help="x-api-key (env API_KEY / SSM api/key)")
    parser.add_argument("--phone", help="nomor demo (env DEMO_PHONE_E164 / SSM)")
    parser.add_argument(
        "--channel", default="email", choices=["whatsapp", "sms", "email"]
    )
    parser.add_argument(
        "--no-reset", action="store_true", help="jangan panggil /demo/reset"
    )
    parser.add_argument(
        "--min-rate", type=float, default=0.9, help="ambang lulus total (0.9)"
    )
    parser.add_argument(
        "--turn-timeout", type=float, default=150.0, help="detik per giliran"
    )
    parser.add_argument(
        "--poll", type=float, default=3.0, help="interval polling detik"
    )
    parser.add_argument(
        "--output", type=Path, help="simpan laporan markdown (docs/evidence/)"
    )
    parser.add_argument(
        "--validate", action="store_true", help="hanya validasi golden.yaml (offline)"
    )
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs minimal 1")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        conversations = select(load_golden(args.golden), args.cases)
    except (ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.validate:
        critical = [c.id for c in conversations if c.critical]
        print(f"{len(conversations)} percakapan valid; kritis: {', '.join(critical)}")
        return 0
    try:
        api_url = resolve_config(args.api_url, "RESOLVEAI_API_URL")
        api_key = resolve_config(args.api_key, "API_KEY", "api/key")
        phone = resolve_config(args.phone, "DEMO_PHONE_E164", "demo/phone_e164")
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    client = ApiClient(api_url, api_key)
    try:
        scores = run_eval(
            client,
            conversations,
            runs=args.runs,
            phone=phone,
            channel=args.channel,
            reset=not args.no_reset,
            turn_timeout=args.turn_timeout,
            poll=args.poll,
        )
    except (RuntimeError, httpx.HTTPError) as exc:  # demo reset failed
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    report = render_report(scores, args.min_rate)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    ok, _ = summarize(scores, args.min_rate)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
