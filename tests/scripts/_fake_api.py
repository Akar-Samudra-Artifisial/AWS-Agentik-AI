"""In-memory fake of the ResolveAI API for harness tests (``httpx.MockTransport``).

A ``Responder`` plays the agent: it is called for each customer message / approval
decision and returns a ``Turn`` (tools called, resulting case fields, reply). The turn's
events become visible only after ``delay`` polls, to exercise the polling loop.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

API_KEY = "test-key"


@dataclass
class Turn:
    tools: dict[str, str] = field(default_factory=dict)  # tool -> output JSON text
    case: dict[str, Any] = field(default_factory=dict)
    reply: str | None = "Baik, kami bantu."
    approval: dict[str, Any] | None = None


Responder = Callable[[str, str, dict[str, Any]], Turn]


@dataclass
class FakeApi:
    responder: Responder
    delay: int = 1
    reset_status: int = 200
    requests: list[httpx.Request] = field(default_factory=list)
    resets: int = 0
    cases: dict[str, dict[str, Any]] = field(default_factory=dict)
    _pending: list[tuple[str, Turn]] = field(default_factory=list)
    _hold: int = 0
    _ts: int = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _tick(self) -> str:
        self._ts += 1
        return f"2026-10-27T00:00:{self._ts:02d}Z"

    def _open_case(self) -> dict[str, Any] | None:
        for detail in self.cases.values():
            if detail["case"]["status"] not in ("resolved", "escalated", "error"):
                return detail
        return None

    def _apply(self, case_id: str, turn: Turn) -> None:
        detail = self.cases[case_id]
        for tool, output in turn.tools.items():
            detail["events"].append(
                {"type": "tool_call", "tool": tool, "ts": self._tick()}
            )
            detail["events"].append(
                {
                    "type": "tool_result",
                    "tool": tool,
                    "output": output,
                    "ts": self._tick(),
                }
            )
        detail["case"].update(turn.case)
        if turn.approval:
            detail["approvals"].append(turn.approval)
        if turn.reply:
            detail["messages"].append(
                {
                    "direction": "outbound",
                    "author": "agent",
                    "body": turn.reply,
                    "ts": self._tick(),
                }
            )
        detail["events"].append({"type": "model_message", "ts": self._tick()})

    def _schedule(self, case_id: str, turn: Turn) -> None:
        self._pending.append((case_id, turn))
        self._hold = self.delay

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("x-api-key") != API_KEY:
            return httpx.Response(
                401, json={"error": {"code": "unauthorized", "message": "x"}}
            )
        path, method = request.url.path, request.method
        if method == "POST" and path == "/api/demo/reset":
            self.resets += 1
            if self.reset_status != 200:
                return httpx.Response(
                    self.reset_status, json={"error": {"code": "x", "message": "x"}}
                )
            self.cases.clear()
            return httpx.Response(200, json={"ok": True})
        if method == "POST" and path == "/api/simulate/inbound":
            body = json.loads(request.content)
            detail = self._open_case()
            if detail is None:
                case_id = f"CASE-TEST-{len(self.cases) + 1:04d}"
                detail = {
                    "case": {"case_id": case_id, "status": "open", "priority": "normal",
                             "resolution_type": None},
                    "messages": [], "events": [], "approvals": [],
                }  # fmt: skip
                self.cases[case_id] = detail
            case_id = detail["case"]["case_id"]
            detail["messages"].append(
                {
                    "direction": "inbound",
                    "author": "customer",
                    "body": body["text"],
                    "ts": self._tick(),
                }
            )
            self._schedule(case_id, self.responder("customer", body["text"], detail))
            return httpx.Response(202, json={"event_id": "ev", "case_id": case_id})
        if method == "POST" and path.startswith("/api/approvals/"):
            approval_id = path.split("/")[3]
            decision = json.loads(request.content)["decision"]
            for detail in self.cases.values():
                for approval in detail["approvals"]:
                    if approval["approval_id"] == approval_id:
                        approval["status"] = (
                            "approved" if decision == "approve" else "rejected"
                        )
                        case_id = detail["case"]["case_id"]
                        self._schedule(
                            case_id, self.responder("approval", decision, detail)
                        )
                        return httpx.Response(
                            202,
                            json={
                                "approval_id": approval_id,
                                "status": approval["status"],
                            },
                        )
            return httpx.Response(
                404, json={"error": {"code": "not_found", "message": "x"}}
            )
        if method == "GET" and path.startswith("/api/cases/"):
            case_id = path.rsplit("/", 1)[1]
            if self._hold > 0:
                self._hold -= 1
            else:
                for pending_case, turn in self._pending:
                    self._apply(pending_case, turn)
                self._pending.clear()
            if case_id not in self.cases:
                return httpx.Response(
                    404, json={"error": {"code": "not_found", "message": "x"}}
                )
            return httpx.Response(200, json=self.cases[case_id])
        return httpx.Response(
            404, json={"error": {"code": "not_found", "message": path}}
        )


def scripted_agent(source: str, value: str, detail: dict[str, Any]) -> Turn:
    """Well-behaved agent for the demo scenarios A, B (approve/reject) and C."""
    if source == "approval":
        if value == "approve":
            return Turn(
                tools={"execute_refund": '{"ok": true, "status": "executed"}',
                       "send_resolution_notice": '{"ok": true}'},
                case={"status": "resolved", "resolution_type": "approved_by_staff"},
                reply="Refund disetujui.",
            )  # fmt: skip
        return Turn(
            tools={"send_message": '{"ok": true}', "escalate_to_human": '{"ok": true}'},
            case={"status": "escalated", "resolution_type": "escalated"},
            reply="Mohon maaf, refund belum dapat disetujui.",
        )
    if "ORD-1001" in value:
        return Turn(
            tools={"get_order": "{}", "search_policy": "{}"},
            case={"status": "awaiting_customer"},
            reply="Pilih: 1) jadwal ulang 2) voucher 3) staf",
        )
    if value == "1":
        return Turn(
            tools={"schedule_redelivery": "{}", "send_resolution_notice": "{}"},
            case={"status": "resolved", "resolution_type": "auto_resolved"},
        )
    if "ORD-1002" in value:
        return Turn(tools={"get_order": "{}"}, case={"status": "awaiting_customer"})
    if "refund" in value.lower():
        return Turn(
            tools={"request_refund": '{"ok": true, "status": "pending_approval"}'},
            case={"status": "awaiting_approval"},
            approval={"approval_id": "APR-0001", "status": "pending"},
            reply="Sedang diverifikasi tim.",
        )
    if "ORD-1003" in value:
        return Turn(
            tools={"escalate_to_human": "{}"},
            case={"status": "escalated", "priority": "high"},
        )
    return Turn()
