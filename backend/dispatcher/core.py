"""Dispatcher core flow (``02-backend.md`` §4, §7, §8), independent of the Lambda handler.

``ingest_inbound`` covers steps 1-5 (dedupe, customer upsert, case reuse/create, store
message) and is reused synchronously by ``POST /api/simulate/inbound``.
``run_agent_turn`` covers steps 6-9 (lock, payload, invoke, release) plus the fail-safe
path. ``handle_event`` routes SNS records and direct payloads.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from resolveai_common.logging import get_logger
from resolveai_common.models import (
    AgentEvent,
    AgentEventType,
    Approval,
    Case,
    CaseStatus,
    Channel,
    Customer,
    DeliveryStatus,
    Message,
    MessageAuthor,
    MessageDirection,
    ProcessedEvent,
)
from resolveai_common.policy import CASE_REUSE_WINDOW_HOURS
from resolveai_common.repository import (
    CASE_LOCK_TTL_SECONDS,
    CaseLockedError,
    CaseNotFoundError,
    DuplicateEventError,
)
from services.agent_client import session_id_for_case
from services.config import now_iso, parse_iso, to_iso
from services.data import (
    set_case_first_inbound,
    set_case_first_response,
    update_case_fields,
)
from services.deps import Deps

from .inbound import NormalizedInbound, parse_whatsapp_sns_message

__all__ = [
    "FAILSAFE_TEXT",
    "HISTORY_LIMIT",
    "IngestResult",
    "TurnResult",
    "build_agent_payload",
    "fail_safe",
    "handle_event",
    "ingest_inbound",
    "new_case_id",
    "process_agent_turn",
    "process_approval_decided",
    "process_inbound",
    "run_agent_turn",
]

FAILSAFE_TEXT = "Maaf, ada kendala teknis. Tim kami akan segera menghubungi Anda."
FAILSAFE_SUBJECT = "[ResolveAI] Kendala teknis"
HISTORY_LIMIT = 20
PROCESSED_EVENT_TTL_DAYS = 7
NEW_CUSTOMER_NAME = "Pelanggan baru"
_EVENT_OUTPUT_MAX = 4096

# A case in one of these statuses is closed for reuse (BE-006).
_NON_REUSABLE = frozenset({CaseStatus.RESOLVED, CaseStatus.ESCALATED, CaseStatus.ERROR})

_log = get_logger(__name__)


@dataclass(frozen=True)
class IngestResult:
    """Outcome of steps 1-5. ``duplicate`` means the event was already processed."""

    duplicate: bool
    case: Case | None = None
    customer: Customer | None = None
    message: Message | None = None


@dataclass(frozen=True)
class TurnResult:
    """Outcome of an agent turn: ``ok``, ``locked``, ``failsafe`` or ``missing_case``."""

    status: str
    case_id: str
    response: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Steps 1-5
# --------------------------------------------------------------------------- #


def _mark_processed(deps: Deps, event_id: str) -> bool:
    """Record ``event_id``; return ``False`` when it was already processed (dedupe)."""
    ttl = int(time.time()) + PROCESSED_EVENT_TTL_DAYS * 86400
    try:
        deps.repos.processed_events.mark_processed(
            ProcessedEvent(event_id=event_id, ttl=ttl)
        )
    except DuplicateEventError:
        _log.info("duplicate event skipped", extra={"event_id": event_id})
        return False
    return True


def _upsert_customer(deps: Deps, phone_e164: str, now: str) -> Customer:
    existing = deps.repos.customers.find_by_phone(phone_e164)
    if existing is not None:
        return existing
    customer = Customer(
        customer_id=f"CUST-{uuid.uuid4().hex[:8].upper()}",
        name=NEW_CUSTOMER_NAME,
        phone_e164=phone_e164,
        created_at=now,
    )
    deps.repos.customers.put(customer)
    _log.info("customer created", extra={"customer_id": customer.customer_id})
    return customer


def new_case_id(deps: Deps, now: datetime) -> str:
    """Generate an unused ``CASE-YYYYMMDD-xxxx`` id."""
    for _ in range(10):
        case_id = f"CASE-{now:%Y%m%d}-{secrets.token_hex(2).upper()}"
        if deps.repos.cases.get(case_id) is None:
            return case_id
    raise RuntimeError("could not allocate a unique case id after 10 attempts")


def _find_or_create_case(
    deps: Deps, customer: Customer, channel: Channel, now: str
) -> Case:
    now_dt = parse_iso(now)
    window_start = now_dt - timedelta(hours=CASE_REUSE_WINDOW_HOURS)
    for case in deps.repos.cases.find_by_customer(customer.customer_id):
        if case.status in _NON_REUSABLE:
            continue
        if parse_iso(case.updated_at) >= window_start:
            return case
    case = Case(
        case_id=new_case_id(deps, now_dt),
        customer_id=customer.customer_id,
        channel=channel,
        created_at=now,
        updated_at=now,
    )
    deps.repos.cases.put(case)
    _log.info("case created", extra={"case_id": case.case_id})
    return case


def ingest_inbound(deps: Deps, inbound: NormalizedInbound) -> IngestResult:
    """Dedupe, upsert customer, find/create case and store the inbound message."""
    if not _mark_processed(deps, inbound.event_id):
        return IngestResult(duplicate=True)

    now = now_iso()
    customer = _upsert_customer(deps, inbound.from_e164, now)
    case = _find_or_create_case(deps, customer, inbound.channel, now)
    message = Message(
        case_id=case.case_id,
        msg_id=uuid.uuid4().hex,
        ts=inbound.received_at,
        direction=MessageDirection.INBOUND,
        author=MessageAuthor.CUSTOMER,
        channel=inbound.channel,
        body=inbound.text,
        provider_message_id=inbound.provider_message_id,
        delivery_status=DeliveryStatus.DELIVERED,
        simulated=inbound.simulated,
        created_at=now,
    )
    deps.repos.messages.put(message)
    set_case_first_inbound(deps.table("cases"), case.case_id, now)
    get_logger(__name__, case.case_id).info(
        "inbound stored",
        extra={"event_id": inbound.event_id, "channel": inbound.channel.value},
    )
    return IngestResult(duplicate=False, case=case, customer=customer, message=message)


# --------------------------------------------------------------------------- #
# Steps 6-9 and fail-safe
# --------------------------------------------------------------------------- #


def _customer_payload(customer: Customer | None) -> dict[str, Any]:
    if customer is None:
        return {}
    return {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "phone_e164": customer.phone_e164,
        "email": customer.email or "",
        "language": customer.language.value,
        "preferred_channel": customer.preferred_channel.value,
    }


def build_agent_payload(
    deps: Deps,
    case: Case,
    customer: Customer | None,
    event_type: str,
    *,
    message: Message | None = None,
    approval: Approval | None = None,
) -> dict[str, Any]:
    """Build the ``02-backend.md`` §8 invocation payload with the last 20 messages."""
    # One extra so the current message can be excluded and still leave HISTORY_LIMIT.
    recent = deps.repos.messages.list_for_case(
        case.case_id, limit=HISTORY_LIMIT + 1, newest=True
    )
    history = [m for m in recent if message is None or m.msg_id != message.msg_id][
        -HISTORY_LIMIT:
    ]
    payload: dict[str, Any] = {
        "event_type": event_type,
        "case_id": case.case_id,
        "customer": _customer_payload(customer),
        "channel": (message.channel if message else case.channel).value,
        "history": [
            {
                "direction": m.direction.value,
                "author": m.author.value,
                "channel": m.channel.value,
                "body": m.body,
                "ts": m.ts,
            }
            for m in history
        ],
    }
    if message is not None:
        payload["message"] = {"text": message.body, "received_at": message.ts}
    if approval is not None:
        payload["approval"] = {
            "approval_id": approval.approval_id,
            "status": approval.status.value,
            "note": approval.note or "",
        }
    return payload


def _next_event_seq(deps: Deps, case_id: str) -> int:
    return len(deps.repos.agent_events.list_for_case(case_id))


def _record_event(
    deps: Deps, case_id: str, event_type: AgentEventType, output: str, *, ok: bool
) -> None:
    deps.repos.agent_events.put(
        AgentEvent(
            case_id=case_id,
            ts=now_iso(),
            seq=_next_event_seq(deps, case_id),
            type=event_type,
            tool="dispatcher",
            output=output[:_EVENT_OUTPUT_MAX],
            ok=ok,
        )
    )


def _failsafe_already_sent(deps: Deps, case_id: str) -> bool:
    return any(
        m.direction is MessageDirection.OUTBOUND
        and m.author is MessageAuthor.SYSTEM
        and m.body == FAILSAFE_TEXT
        for m in deps.repos.messages.list_for_case(case_id)
    )


def _channel_order(first: Channel) -> list[Channel]:
    return [first] + [
        c for c in (Channel.WHATSAPP, Channel.SMS, Channel.EMAIL) if c != first
    ]


def _send_failsafe_message(deps: Deps, case: Case, customer: Customer) -> None:
    log = get_logger(__name__, case.case_id)
    try:
        attempts = deps.sender(
            text=FAILSAFE_TEXT,
            to_e164=customer.phone_e164,
            to_email=customer.email,
            subject=FAILSAFE_SUBJECT,
            order=_channel_order(case.channel),
        )
    except Exception:
        log.exception("fail-safe send raised")
        return
    for attempt in attempts:
        now = now_iso()
        deps.repos.messages.put(
            Message(
                case_id=case.case_id,
                msg_id=uuid.uuid4().hex,
                ts=now,
                direction=MessageDirection.OUTBOUND,
                author=MessageAuthor.SYSTEM,
                channel=attempt.channel,
                body=FAILSAFE_TEXT,
                provider_message_id=attempt.provider_message_id,
                delivery_status=DeliveryStatus.SENT
                if attempt.ok
                else DeliveryStatus.FAILED,
                error=attempt.error,
                created_at=now,
            )
        )
        if attempt.ok:
            set_case_first_response(deps.table("cases"), case.case_id, now)
    log.info(
        "fail-safe message attempts",
        extra={"attempts": [(a.channel.value, a.ok) for a in attempts]},
    )


def fail_safe(deps: Deps, case: Case, customer: Customer | None, reason: str) -> None:
    """``02-backend.md`` §7: mark error, apologize once, escalate with high priority."""
    log = get_logger(__name__, case.case_id)
    log.error("agent turn failed, running fail-safe", extra={"reason": reason})
    cases_table = deps.table("cases")
    update_case_fields(
        cases_table,
        case.case_id,
        {"status": CaseStatus.ERROR.value, "updated_at": now_iso()},
    )
    _record_event(deps, case.case_id, AgentEventType.ERROR, reason, ok=False)

    if customer is not None and not _failsafe_already_sent(deps, case.case_id):
        _send_failsafe_message(deps, case, customer)

    update_case_fields(
        cases_table,
        case.case_id,
        {
            "status": CaseStatus.ESCALATED.value,
            "priority": "high",
            "resolution_type": "escalated",
            "updated_at": now_iso(),
        },
    )
    _record_event(
        deps,
        case.case_id,
        AgentEventType.ESCALATION,
        "escalated by dispatcher fail-safe (priority high)",
        ok=True,
    )


def run_agent_turn(
    deps: Deps,
    case_id: str,
    event_type: str,
    *,
    message: Message | None = None,
    approval: Approval | None = None,
) -> TurnResult:
    """Lock the case, invoke the agent, release the lock; fail-safe on errors."""
    log = get_logger(__name__, case_id)
    case = deps.repos.cases.get(case_id)
    if case is None:
        log.error("case not found for agent turn")
        return TurnResult(status="missing_case", case_id=case_id)
    customer = deps.repos.customers.get(case.customer_id)

    now_dt = datetime.now(UTC)
    lock_until = to_iso(now_dt + timedelta(seconds=CASE_LOCK_TTL_SECONDS))
    try:
        deps.repos.cases.acquire_lock(
            case_id, lock_until=lock_until, now=to_iso(now_dt)
        )
    except CaseLockedError:
        # P0 of BE-007: refuse the parallel turn safely; the message is already stored.
        log.warning("case locked, turn skipped", extra={"event_type": event_type})
        return TurnResult(status="locked", case_id=case_id)
    except CaseNotFoundError:
        # Case deleted between get() and lock (e.g. demo reset); nothing to process.
        log.error("case vanished before lock")
        return TurnResult(status="missing_case", case_id=case_id)

    try:
        payload = build_agent_payload(
            deps, case, customer, event_type, message=message, approval=approval
        )
        started = time.monotonic()
        try:
            response = deps.invoker.invoke(payload, session_id_for_case(case_id))
        except Exception as exc:  # noqa: BLE001 - any invoker failure must reach fail-safe (§7)
            fail_safe(deps, case, customer, f"agent invocation failed: {exc}")
            return TurnResult(status="failsafe", case_id=case_id)
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.get("error"):
            fail_safe(
                deps, case, customer, f"agent returned error: {response['error']}"
            )
            return TurnResult(status="failsafe", case_id=case_id, response=response)
        log.info(
            "agent turn completed",
            extra={
                "event_type": event_type,
                "latency_ms": latency_ms,
                "case_status": response.get("case_status"),
                "actions": response.get("actions"),
            },
        )
        return TurnResult(status="ok", case_id=case_id, response=response)
    finally:
        deps.repos.cases.release_lock(case_id, now=now_iso())


def process_inbound(deps: Deps, inbound: NormalizedInbound) -> TurnResult | None:
    """Full flow for one inbound message; ``None`` when it was a duplicate."""
    ingested = ingest_inbound(deps, inbound)
    if ingested.duplicate or ingested.case is None:
        return None
    return run_agent_turn(
        deps, ingested.case.case_id, "customer_message", message=ingested.message
    )


def process_approval_decided(
    deps: Deps, approval_id: str, decided_at: str
) -> TurnResult | None:
    """Invoke the agent with ``approval_decided``; deduped on ``approval_id#decided_at``."""
    if not _mark_processed(deps, f"{approval_id}#{decided_at}"):
        return None
    approval = deps.repos.approvals.get(approval_id)
    if approval is None:
        _log.error("approval not found", extra={"approval_id": approval_id})
        return None
    return run_agent_turn(deps, approval.case_id, "approval_decided", approval=approval)


def process_agent_turn(
    deps: Deps, event_id: str, case_id: str, msg_id: str
) -> TurnResult | None:
    """Agent turn for a message already ingested by the API (simulate inbound)."""
    if not _mark_processed(deps, f"turn#{event_id}"):
        return None
    message = next(
        (m for m in deps.repos.messages.list_for_case(case_id) if m.msg_id == msg_id),
        None,
    )
    return run_agent_turn(deps, case_id, "customer_message", message=message)


# --------------------------------------------------------------------------- #
# Event routing
# --------------------------------------------------------------------------- #


def handle_event(deps: Deps, event: dict[str, Any]) -> dict[str, Any]:
    """Route an SNS event or a direct payload (``simulate_inbound``, ``agent_turn``,
    ``approval_decided``) and return a small summary for logs/tests."""
    results: list[TurnResult | None] = []

    if "Records" in event:
        for record in event["Records"]:
            sns = record.get("Sns") or {}
            for inbound in parse_whatsapp_sns_message(sns.get("Message", "")):
                results.append(process_inbound(deps, inbound))
    else:
        event_type = event.get("type")
        if event_type == "simulate_inbound":
            results.append(
                process_inbound(
                    deps, NormalizedInbound.model_validate(event["inbound"])
                )
            )
        elif event_type == "agent_turn":
            results.append(
                process_agent_turn(
                    deps, event["event_id"], event["case_id"], event["msg_id"]
                )
            )
        elif event_type == "approval_decided":
            results.append(
                process_approval_decided(
                    deps, event["approval_id"], event["decided_at"]
                )
            )
        else:
            raise ValueError(f"unsupported dispatcher event type: {event_type!r}")

    return {
        "processed": sum(1 for r in results if r is not None),
        "skipped": sum(1 for r in results if r is None),
        "turns": [
            {"case_id": r.case_id, "status": r.status} for r in results if r is not None
        ],
    }
