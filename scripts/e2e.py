#!/usr/bin/env python3
"""End-to-end test against the deployed stack (TST-002, ``07-testing-demo.md`` §2).

Scenarios A, B-approve, B-reject and C are played through the API
(``POST /api/simulate/inbound`` + ``POST /api/approvals/{id}/decision``) and the case is
polled until each agent turn finishes; then status, tool events, approvals and outbound
messages are asserted. Prints a pass/fail table; exit code 0 only when all pass.

Scenarios share the demo customer and mutate seed orders, so pass ``--reset`` to call
``POST /api/demo/reset`` before each scenario (or run ``make seed`` and close open
cases between runs). Real messages are sent to the demo contact on ``--channel``.

Configuration (argument → env → SSM ``/resolveai/dev/...``):
    --api-url  RESOLVEAI_API_URL   (CDK output ``api-url``)
    --api-key  API_KEY             api/key
    --phone    DEMO_PHONE_E164     demo/phone_e164

Examples:
    python scripts/e2e.py --reset
    python scripts/e2e.py --reset --only A,C --channel email
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx
from _config import ConfigError, resolve_config
from _harness import (
    ApiClient,
    Conversation,
    Expectation,
    Outcome,
    Step,
    run_conversation,
)

__all__ = ["SCENARIOS", "main", "render_report", "run_scenarios"]

_A_MSG = "Halo, pesanan ORD-1001 saya sudah lewat 2 hari dari estimasi tapi belum sampai juga."
_B_MSGS = (
    Step(
        customer="Paket ORD-1002 saya tidak ada update tracking hampir seminggu, sepertinya hilang."
    ),
    Step(customer="Saya pilih refund saja."),
)

SCENARIOS: tuple[Conversation, ...] = (
    Conversation(
        id="A",
        title="Terlambat 2 hari → opsi → pilih 1 (jadwal ulang)",
        steps=(Step(customer=_A_MSG), Step(customer="1")),
        expect=Expectation(
            tools_called=(
                "get_order",
                "search_policy",
                "schedule_redelivery",
                "send_resolution_notice",
            ),
            tools_not_called=("request_refund", "execute_refund"),
            status_in=("resolved",),
            resolution_type_in=("auto_resolved",),
            min_outbound=2,
        ),
    ),
    Conversation(
        id="B-approve",
        title="Paket hilang Rp349.000 → refund → staf approve",
        steps=(*_B_MSGS, Step(approval="approve")),
        expect=Expectation(
            tools_called=("request_refund", "execute_refund", "send_resolution_notice"),
            tool_output_contains={"request_refund": "pending_approval"},
            status_in=("resolved",),
            resolution_type_in=("approved_by_staff",),
            approval_status_in=("approved",),
            min_outbound=2,
        ),
    ),
    Conversation(
        id="B-reject",
        title="Paket hilang Rp349.000 → refund → staf reject",
        steps=(*_B_MSGS, Step(approval="reject")),
        expect=Expectation(
            tools_called=("request_refund", "escalate_to_human"),
            tools_not_called=("execute_refund",),
            status_in=("escalated",),
            approval_status_in=("rejected",),
            min_outbound=2,
        ),
    ),
    Conversation(
        id="C",
        title="Delivered tapi tidak diterima + ancaman polisi → eskalasi",
        steps=(
            Step(
                customer="Pesanan ORD-1003 katanya delivered tapi saya tidak menerima apa pun! "
                "Saya akan lapor polisi."
            ),
        ),
        expect=Expectation(
            tools_called=("escalate_to_human",),
            tools_not_called=("create_voucher", "request_refund", "execute_refund"),
            status_in=("escalated",),
            priority_in=("high",),
            min_outbound=1,
        ),
    ),
)


def select(only: str | None) -> list[Conversation]:
    if not only:
        return list(SCENARIOS)
    wanted = [s.strip() for s in only.split(",") if s.strip()]
    known = {s.id for s in SCENARIOS}
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise ValueError(
            f"skenario tidak dikenal: {', '.join(unknown)} (pilihan: {sorted(known)})"
        )
    return [s for s in SCENARIOS if s.id in wanted]


def run_scenarios(
    client: ApiClient,
    scenarios: Sequence[Conversation],
    *,
    phone: str,
    channel: str,
    reset: bool,
    turn_timeout: float,
    poll: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> list[tuple[Outcome, float]]:
    results: list[tuple[Outcome, float]] = []
    for scenario in scenarios:
        started = clock()
        if reset:
            try:
                client.demo_reset()
            except (RuntimeError, httpx.HTTPError) as exc:
                outcome = Outcome(scenario.id, failures=[f"demo reset gagal: {exc}"])
                results.append((outcome, clock() - started))
                continue
        outcome = run_conversation(
            client,
            scenario,
            phone=phone,
            channel=channel,
            decided_by="e2e-script",
            turn_timeout=turn_timeout,
            poll=poll,
            sleep=sleep,
            clock=clock,
        )
        results.append((outcome, clock() - started))
    return results


def render_report(results: Sequence[tuple[Outcome, float]]) -> str:
    rows = ["| Skenario | Hasil | Kasus | Durasi | Catatan |", "|---|---|---|---|---|"]
    for outcome, elapsed in results:
        rows.append(
            f"| {outcome.conversation_id} | {'LULUS' if outcome.passed else 'GAGAL'} | "
            f"{outcome.case_id or '-'} | {elapsed:.0f}s | "
            f"{'; '.join(outcome.failures).replace('|', '/')} |"
        )
    passed = sum(o.passed for o, _ in results)
    rows += ["", f"E2E: {passed}/{len(results)} skenario lulus"]
    return "\n".join(rows)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E2E skenario A, B-approve, B-reject, C via API."
    )
    parser.add_argument("--api-url", help="base URL API (env RESOLVEAI_API_URL)")
    parser.add_argument("--api-key", help="x-api-key (env API_KEY / SSM api/key)")
    parser.add_argument("--phone", help="nomor demo (env DEMO_PHONE_E164 / SSM)")
    parser.add_argument(
        "--channel", default="whatsapp", choices=["whatsapp", "sms", "email"]
    )
    parser.add_argument("--only", help="subset skenario, mis. A,C")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="POST /api/demo/reset sebelum tiap skenario",
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        scenarios = select(args.only)
        api_url = resolve_config(args.api_url, "RESOLVEAI_API_URL")
        api_key = resolve_config(args.api_key, "API_KEY", "api/key")
        phone = resolve_config(args.phone, "DEMO_PHONE_E164", "demo/phone_e164")
    except (ValueError, ConfigError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not args.reset:
        print(
            "PERINGATAN: tanpa --reset; pastikan data seed segar dan tidak ada kasus terbuka."
        )
    client = ApiClient(api_url, api_key)
    try:
        results = run_scenarios(
            client,
            scenarios,
            phone=phone,
            channel=args.channel,
            reset=args.reset,
            turn_timeout=args.turn_timeout,
            poll=args.poll,
        )
    finally:
        client.close()
    report = render_report(results)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("# E2E\n\n" + report + "\n", encoding="utf-8")
    return 0 if all(o.passed for o, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
