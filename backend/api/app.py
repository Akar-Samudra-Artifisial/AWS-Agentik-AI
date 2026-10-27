"""FastAPI app for the dashboard (``02-backend.md`` §5) and its Mangum Lambda handler."""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from dispatcher.core import ingest_inbound
from dispatcher.inbound import NormalizedInbound
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from resolveai_common.logging import configure_root_logger, get_logger
from resolveai_common.models import (
    Approval,
    ApprovalStatus,
    Case,
    CaseStatus,
    Channel,
    Customer,
    Message,
)
from resolveai_common.phone import normalize_phone
from resolveai_common.repository import MESSAGES_SORT_KEY
from services.config import ConfigError, get_param, now_iso
from services.data import ApprovalAlreadyDecidedError, decide_approval, scan_all
from services.demo_reset import DEMO_RESET_ENV, is_demo_reset_enabled, reset_demo
from services.deps import Deps, build_default_deps
from services.trigger import Trigger, build_default_trigger
from starlette.exceptions import HTTPException as StarletteHTTPException

from .metrics import compute_metrics
from .schemas import (
    ApprovalWithCase,
    CaseDetail,
    CaseSummary,
    DecisionRequest,
    DecisionResponse,
    DemoResetDeleted,
    DemoResetResponse,
    ErrorResponse,
    HealthResponse,
    Metrics,
    SimulateInboundRequest,
    SimulateInboundResponse,
)

__all__ = ["ApiError", "app", "create_app", "handler"]

_log = get_logger(__name__)

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    500: "internal_error",
}
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (400, 401, 404, 409, 500)
}


class ApiError(Exception):
    """Error rendered as ``{error:{code,message}}`` with the given HTTP status."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def _deps(request: Request) -> Deps:
    return request.app.state.deps_provider()


def _trigger(request: Request) -> Trigger:
    return request.app.state.trigger


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Constant-time compare of ``x-api-key`` against SSM ``api/key`` (or env ``API_KEY``)."""
    try:
        expected = get_param("api/key", "API_KEY")
    except ConfigError as exc:
        _log.error("api key not configured", extra={"error": str(exc)})
        raise ApiError(500, "config_error", "API key is not configured") from exc
    if not x_api_key or not hmac.compare_digest(
        x_api_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise ApiError(401, "unauthorized", "missing or invalid x-api-key")


DepsDep = Annotated[Deps, Depends(_deps)]
TriggerDep = Annotated[Trigger, Depends(_trigger)]


def _scan_cases(deps: Deps) -> list[Case]:
    return [Case.model_validate(item) for item in scan_all(deps.table("cases"))]


def _scan_approvals(deps: Deps) -> list[Approval]:
    return [Approval.model_validate(item) for item in scan_all(deps.table("approvals"))]


def _scan_messages(deps: Deps) -> list[Message]:
    return [
        Message.model_validate({k: v for k, v in item.items() if k != MESSAGES_SORT_KEY})
        for item in scan_all(deps.table("messages"))
    ]


def _summaries(deps: Deps, cases: list[Case]) -> list[CaseSummary]:
    names: dict[str, str | None] = {}
    summaries: list[CaseSummary] = []
    for case in cases:
        if case.customer_id not in names:
            customer: Customer | None = deps.repos.customers.get(case.customer_id)
            names[case.customer_id] = customer.name if customer else None
        summaries.append(
            CaseSummary(
                case_id=case.case_id,
                status=case.status,
                category=case.category,
                priority=case.priority,
                channel=case.channel,
                customer_name=names[case.customer_id],
                order_id=case.order_id,
                summary=case.summary,
                created_at=case.created_at,
                updated_at=case.updated_at,
                resolution_type=case.resolution_type,
            )
        )
    return summaries


def _build_router() -> APIRouter:
    public = APIRouter(prefix="/api")
    router = APIRouter(
        prefix="/api",
        dependencies=[Depends(require_api_key)],
        responses=_ERROR_RESPONSES,
    )

    @public.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @router.get("/cases", response_model=list[CaseSummary])
    def list_cases(
        deps: DepsDep,
        status: CaseStatus | None = None,
        channel: Channel | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[CaseSummary]:
        cases = deps.repos.cases.find_by_status(status) if status else _scan_cases(deps)
        if channel:
            cases = [c for c in cases if c.channel is channel]
        cases.sort(key=lambda c: c.updated_at, reverse=True)
        return _summaries(deps, cases[:limit])

    @router.get("/cases/{case_id}", response_model=CaseDetail)
    def get_case(case_id: str, deps: DepsDep) -> CaseDetail:
        case = deps.repos.cases.get(case_id)
        if case is None:
            raise ApiError(404, "not_found", f"case {case_id} not found")
        return CaseDetail(
            case=case,
            customer=deps.repos.customers.get(case.customer_id),
            order=deps.repos.orders.get(case.order_id) if case.order_id else None,
            messages=deps.repos.messages.list_for_case(case_id),
            events=deps.repos.agent_events.list_for_case(case_id),
            approvals=[a for a in _scan_approvals(deps) if a.case_id == case_id],
        )

    @router.get("/approvals", response_model=list[ApprovalWithCase])
    def list_approvals(
        deps: DepsDep, status: ApprovalStatus = ApprovalStatus.PENDING
    ) -> list[ApprovalWithCase]:
        result: list[ApprovalWithCase] = []
        for approval in deps.repos.approvals.find_by_status(status):
            case = deps.repos.cases.get(approval.case_id)
            summary = _summaries(deps, [case])[0] if case else None
            result.append(ApprovalWithCase(**approval.model_dump(), case=summary))
        return result

    @router.post(
        "/approvals/{approval_id}/decision",
        status_code=202,
        response_model=DecisionResponse,
    )
    def decide(
        approval_id: str, body: DecisionRequest, deps: DepsDep, trigger: TriggerDep
    ) -> DecisionResponse:
        if deps.repos.approvals.get(approval_id) is None:
            raise ApiError(404, "not_found", f"approval {approval_id} not found")
        status = (
            ApprovalStatus.APPROVED
            if body.decision == "approve"
            else ApprovalStatus.REJECTED
        )
        decided_at = now_iso()
        try:
            approval = decide_approval(
                deps.table("approvals"),
                approval_id,
                status=status.value,
                decided_at=decided_at,
                decided_by=body.decided_by,
                note=body.note,
            )
        except ApprovalAlreadyDecidedError as exc:
            raise ApiError(
                409, "conflict", f"approval {approval_id} already decided"
            ) from exc
        get_logger(__name__, approval.case_id).info(
            "approval decided",
            extra={"approval_id": approval_id, "status": status.value},
        )
        trigger(
            {
                "type": "approval_decided",
                "approval_id": approval_id,
                "decided_at": decided_at,
            }
        )
        return DecisionResponse(approval_id=approval_id, status=status.value)

    @router.post(
        "/simulate/inbound", status_code=202, response_model=SimulateInboundResponse
    )
    def simulate_inbound(
        body: SimulateInboundRequest, deps: DepsDep, trigger: TriggerDep
    ) -> SimulateInboundResponse:
        from_e164 = normalize_phone(body.from_e164)
        if from_e164 is None:
            raise ApiError(
                400, "validation_error", "from_e164 is not a valid Indonesian number"
            )
        event_id = str(uuid.uuid4())
        ingested = ingest_inbound(
            deps,
            NormalizedInbound(
                event_id=event_id,
                channel=body.channel,
                from_e164=from_e164,
                text=body.text,
                received_at=now_iso(),
                simulated=True,
            ),
        )
        if ingested.case is None or ingested.message is None:
            return SimulateInboundResponse(event_id=event_id)
        trigger(
            {
                "type": "agent_turn",
                "event_id": event_id,
                "case_id": ingested.case.case_id,
                "msg_id": ingested.message.msg_id,
            }
        )
        return SimulateInboundResponse(event_id=event_id, case_id=ingested.case.case_id)

    @router.get("/metrics", response_model=Metrics)
    def metrics(deps: DepsDep) -> Metrics:
        return compute_metrics(
            _scan_cases(deps), _scan_approvals(deps), _scan_messages(deps)
        )

    @router.post(
        "/demo/reset",
        response_model=DemoResetResponse,
        responses={403: {"model": ErrorResponse}},
    )
    def demo_reset(deps: DepsDep) -> DemoResetResponse:
        if not is_demo_reset_enabled():
            raise ApiError(
                403, "forbidden", f"demo reset is disabled (set {DEMO_RESET_ENV}=true)"
            )
        result = reset_demo(deps, datetime.now(UTC))
        _log.info(
            "demo reset",
            extra={"deleted": result.deleted, "reset_orders": result.reset_orders},
        )
        return DemoResetResponse(
            deleted=DemoResetDeleted(**result.deleted),
            reset_orders=result.reset_orders,
        )

    combined = APIRouter()
    combined.include_router(public)
    combined.include_router(router)
    return combined


def create_app(
    deps: Deps | None = None,
    trigger: Trigger | None = None,
) -> FastAPI:
    """Build the app. ``deps``/``trigger`` default to real AWS (built lazily)."""
    app = FastAPI(title="ResolveAI API", version="0.1.0")

    cache: dict[str, Deps] = {}

    def deps_provider() -> Deps:
        if deps is not None:
            return deps
        if "deps" not in cache:
            cache["deps"] = build_default_deps()
        return cache["deps"]

    app.state.deps_provider = deps_provider
    app.state.trigger = trigger or build_default_trigger(deps_provider)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _ERROR_CODES.get(exc.status_code, "error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", ()))
        return _error(
            400, "validation_error", f"{location}: {first.get('msg', 'invalid')}"
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        _log.exception("unhandled API error")
        return _error(500, "internal_error", "internal server error")

    app.include_router(_build_router())
    return app


configure_root_logger()
app = create_app()
handler = Mangum(app, lifespan="off")
