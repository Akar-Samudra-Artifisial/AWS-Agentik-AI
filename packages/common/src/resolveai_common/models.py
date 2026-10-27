"""Pydantic v2 models and enums — the cross-platform data contract for ResolveAI.

Mirrors ``docs/prd/00-overview.md`` §10. Conventions (see ``CLAUDE.md``):
  - Times are ISO 8601 UTC strings (field names ending in ``_at`` or named ``ts``).
  - Money is integer rupiah (fields ending in ``_idr``).
  - IDs are prefixed: ``CUST-``, ``ORD-``, ``CASE-``, ``APR-``.

Derived order values (``days_late``, ``days_since_last_scan``, ``eligibility``) are
computed at ``get_order`` time in the agent layer and are intentionally NOT stored
on the model.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Channel",
    "Language",
    "PreferredChannel",
    "OrderStatus",
    "CaseStatus",
    "CaseCategory",
    "CasePriority",
    "ResolutionType",
    "MessageDirection",
    "MessageAuthor",
    "DeliveryStatus",
    "ApprovalStatus",
    "AgentEventType",
    "Customer",
    "OrderItem",
    "TrackingEvent",
    "RefundInfo",
    "Order",
    "CaseResolution",
    "Case",
    "Message",
    "AgentEvent",
    "Approval",
    "ProcessedEvent",
]


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class Channel(StrEnum):
    """Messaging channel a message was sent or received on."""

    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class Language(StrEnum):
    """Customer language preference."""

    ID = "id"
    EN = "en"


class PreferredChannel(StrEnum):
    """Customer's preferred outbound channel."""

    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class OrderStatus(StrEnum):
    """Lifecycle status of an order."""

    PROCESSING = "processing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class CaseStatus(StrEnum):
    """Lifecycle status of a support case."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    AWAITING_CUSTOMER = "awaiting_customer"
    AWAITING_APPROVAL = "awaiting_approval"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ERROR = "error"


class CaseCategory(StrEnum):
    """Classification of the customer complaint."""

    LATE_DELIVERY = "late_delivery"
    LOST_PACKAGE = "lost_package"
    NOT_RECEIVED = "not_received"
    STATUS_INQUIRY = "status_inquiry"
    ADDRESS_CHANGE = "address_change"
    OTHER = "other"


class CasePriority(StrEnum):
    """Case handling priority."""

    NORMAL = "normal"
    HIGH = "high"


class ResolutionType(StrEnum):
    """How a case was ultimately resolved."""

    AUTO_RESOLVED = "auto_resolved"
    APPROVED_BY_STAFF = "approved_by_staff"
    REJECTED_BY_STAFF = "rejected_by_staff"
    ESCALATED = "escalated"


class MessageDirection(StrEnum):
    """Direction of a message relative to the system."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageAuthor(StrEnum):
    """Who authored a message."""

    CUSTOMER = "customer"
    AGENT = "agent"
    STAFF = "staff"
    SYSTEM = "system"


class DeliveryStatus(StrEnum):
    """Delivery state of an outbound message."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    """Status of a staff approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentEventType(StrEnum):
    """Type of event recorded in the agent timeline."""

    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MODEL_MESSAGE = "model_message"
    ESCALATION = "escalation"
    ERROR = "error"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #

_MODEL_CONFIG = ConfigDict(use_enum_values=False, extra="forbid")


class Customer(BaseModel):
    """A customer record. PK ``customer_id``; GSI ``by_phone`` on ``phone_e164``."""

    model_config = _MODEL_CONFIG

    customer_id: str = Field(description="Prefixed ID, e.g. 'CUST-0001'.")
    name: str
    phone_e164: str = Field(description="E.164 phone, e.g. '+62812...'.")
    email: str | None = None
    language: Language = Language.ID
    preferred_channel: PreferredChannel = PreferredChannel.WHATSAPP
    created_at: str = Field(description="ISO 8601 UTC timestamp.")


class OrderItem(BaseModel):
    """A single line item within an order."""

    model_config = _MODEL_CONFIG

    name: str
    qty: int = Field(ge=1)
    price_idr: int = Field(ge=0, description="Unit price in integer rupiah.")


class TrackingEvent(BaseModel):
    """A courier tracking scan event."""

    model_config = _MODEL_CONFIG

    ts: str = Field(description="ISO 8601 UTC timestamp of the scan.")
    location: str
    desc: str


class RefundInfo(BaseModel):
    """Refund sub-record attached to an order once a refund is initiated."""

    model_config = _MODEL_CONFIG

    status: ApprovalStatus
    amount_idr: int = Field(ge=0)
    at: str = Field(description="ISO 8601 UTC timestamp of the refund decision.")


class Order(BaseModel):
    """An order. PK ``order_id``; GSI ``by_customer`` (``customer_id``, ``created_at``).

    Derived fields (``days_late``, ``days_since_last_scan``, ``eligibility``) are NOT
    stored here; they are computed by the agent at read time.
    """

    model_config = _MODEL_CONFIG

    order_id: str = Field(description="Prefixed ID, e.g. 'ORD-1001'.")
    customer_id: str
    status: OrderStatus
    items: list[OrderItem] = Field(default_factory=list)
    total_idr: int = Field(ge=0, description="Order total in integer rupiah.")
    courier: str | None = None
    tracking_number: str | None = None
    shipped_at: str | None = None
    eta: str | None = Field(default=None, description="Estimated delivery, ISO 8601 UTC.")
    last_scan_at: str | None = None
    last_scan_location: str | None = None
    tracking_events: list[TrackingEvent] = Field(default_factory=list)
    redelivery_at: str | None = None
    refund: RefundInfo | None = None
    created_at: str = Field(description="ISO 8601 UTC timestamp.")


class CaseResolution(BaseModel):
    """Resolution summary attached to a case once it is closed."""

    model_config = _MODEL_CONFIG

    action: str
    amount_idr: int | None = Field(default=None, ge=0)
    voucher_code: str | None = None
    summary: str


class Case(BaseModel):
    """A support case. PK ``case_id``; GSIs ``by_customer`` and ``by_status``."""

    model_config = _MODEL_CONFIG

    case_id: str = Field(description="Prefixed ID, e.g. 'CASE-20261028-0001'.")
    customer_id: str
    order_id: str | None = None
    channel: Channel = Field(description="Channel of the first inbound message.")
    status: CaseStatus = CaseStatus.OPEN
    category: CaseCategory = CaseCategory.OTHER
    priority: CasePriority = CasePriority.NORMAL
    resolution_type: ResolutionType | None = None
    resolution: CaseResolution | None = None
    summary: str = ""
    first_inbound_at: str | None = None
    first_response_at: str | None = None
    resolved_at: str | None = None
    created_at: str = Field(description="ISO 8601 UTC timestamp.")
    updated_at: str = Field(description="ISO 8601 UTC timestamp.")
    lock_until: str | None = Field(default=None, description="ISO 8601 UTC lock expiry.")
    seeded: bool = False


class Message(BaseModel):
    """A conversation message. PK ``case_id``, SK ``ts#msg_id``."""

    model_config = _MODEL_CONFIG

    case_id: str
    msg_id: str
    ts: str = Field(description="ISO 8601 UTC timestamp.")
    direction: MessageDirection
    author: MessageAuthor
    channel: Channel
    body: str
    provider_message_id: str | None = None
    delivery_status: DeliveryStatus = DeliveryStatus.QUEUED
    error: str | None = None
    simulated: bool = False
    created_at: str = Field(description="ISO 8601 UTC timestamp.")


class AgentEvent(BaseModel):
    """An agent timeline event. PK ``case_id``, SK ``ts#seq``.

    ``output`` is truncated to <=4 KB by the writer before persistence.
    """

    model_config = _MODEL_CONFIG

    case_id: str
    ts: str = Field(description="ISO 8601 UTC timestamp.")
    seq: int = Field(ge=0, description="Monotonic sequence within the case.")
    type: AgentEventType
    tool: str | None = None
    input: str | None = None
    output: str | None = Field(default=None, description="Truncated to <=4 KB.")
    latency_ms: int | None = Field(default=None, ge=0)
    ok: bool = True


class Approval(BaseModel):
    """A staff approval request. PK ``approval_id``; GSI ``by_status``."""

    model_config = _MODEL_CONFIG

    approval_id: str = Field(description="Prefixed ID, e.g. 'APR-0001'.")
    case_id: str
    order_id: str
    action: str = Field(default="refund", description="Only 'refund' is supported.")
    amount_idr: int = Field(ge=0)
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = Field(description="ISO 8601 UTC timestamp.")
    decided_at: str | None = None
    decided_by: str | None = None
    note: str | None = None


class ProcessedEvent(BaseModel):
    """Idempotency marker for an inbound event. PK ``event_id`` with TTL."""

    model_config = _MODEL_CONFIG

    event_id: str
    ttl: int = Field(ge=0, description="Unix epoch seconds for DynamoDB TTL expiry.")
