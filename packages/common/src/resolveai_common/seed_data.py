"""Synthetic demo seed data builders (PRD 07 §3, TST-001), shared by seed CLI and API.

Pure functions: every record has a fixed ID and dates relative to ``now`` (UTC ISO 8601).
Money is integer rupiah. Lives in ``resolveai_common`` so ``scripts/seed.py`` and the
``POST /api/demo/reset`` endpoint (Lambda bundle) build identical data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .models import (
    Case,
    CaseCategory,
    CaseResolution,
    CaseStatus,
    Channel,
    Customer,
    Language,
    Order,
    OrderItem,
    OrderStatus,
    PreferredChannel,
    ResolutionType,
    TrackingEvent,
)
from .repository import Repositories

__all__ = [
    "COURIER",
    "DEMO_CUSTOMER_ID",
    "SEEDED_CASE_COUNT",
    "SeedData",
    "build_orders",
    "build_seed_data",
    "seed",
]

COURIER = "NusaExpress"
DEMO_CUSTOMER_ID = "CUST-0001"
SEEDED_CASE_COUNT = 25
# Fixed RNG seed so the synthetic case history is identical on every run.
_RNG_SEED = 20261028


@dataclass(frozen=True)
class SeedData:
    customers: list[Customer]
    orders: list[Order]
    cases: list[Case]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _customers(now: datetime, phone: str, email: str) -> list[Customer]:
    created = _iso(now - timedelta(days=90))
    synthetic = [
        (
            "CUST-0002",
            "Budi Santoso",
            "+6281100000002",
            Language.ID,
            PreferredChannel.WHATSAPP,
        ),
        (
            "CUST-0003",
            "Sari Wulandari",
            "+6281100000003",
            Language.ID,
            PreferredChannel.SMS,
        ),
        (
            "CUST-0004",
            "Andi Pratama",
            "+6281100000004",
            Language.ID,
            PreferredChannel.EMAIL,
        ),
        (
            "CUST-0005",
            "Maya Lestari",
            "+6281100000005",
            Language.EN,
            PreferredChannel.WHATSAPP,
        ),
    ]
    return [
        Customer(
            customer_id=DEMO_CUSTOMER_ID,
            name="Rani",
            phone_e164=phone,
            email=email,
            language=Language.ID,
            preferred_channel=PreferredChannel.WHATSAPP,
            created_at=created,
        ),
        *[
            Customer(
                customer_id=cid,
                name=name,
                phone_e164=cust_phone,
                email=f"{cid.lower()}@example.com",
                language=lang,
                preferred_channel=pref,
                created_at=created,
            )
            for cid, name, cust_phone, lang, pref in synthetic
        ],
    ]


def _order(
    now: datetime,
    order_id: str,
    item: str,
    total_idr: int,
    status: OrderStatus,
    *,
    shipped_days_ago: float | None,
    eta_days: float | None,
    last_scan_days_ago: float | None,
    last_scan_location: str | None = None,
) -> Order:
    """Build a demo order for Rani; ``eta_days`` is relative to now (negative = past)."""
    created = now - timedelta(days=(shipped_days_ago or 0) + 1)
    events: list[TrackingEvent] = []
    if shipped_days_ago is not None:
        events.append(
            TrackingEvent(
                ts=_iso(now - timedelta(days=shipped_days_ago)),
                location="Gudang Jakarta",
                desc="Paket diserahkan ke kurir",
            )
        )
    if last_scan_days_ago is not None and last_scan_days_ago != shipped_days_ago:
        events.append(
            TrackingEvent(
                ts=_iso(now - timedelta(days=last_scan_days_ago)),
                location=last_scan_location or "Hub Bandung",
                desc="Diterima penerima" if status is OrderStatus.DELIVERED else "Paket transit",
            )
        )
    shipped = shipped_days_ago is not None
    return Order(
        order_id=order_id,
        customer_id=DEMO_CUSTOMER_ID,
        status=status,
        items=[OrderItem(name=item, qty=1, price_idr=total_idr)],
        total_idr=total_idr,
        courier=COURIER if shipped else None,
        tracking_number=f"NX{order_id.removeprefix('ORD-')}88" if shipped else None,
        shipped_at=_iso(now - timedelta(days=shipped_days_ago)) if shipped else None,
        eta=_iso(now + timedelta(days=eta_days)) if eta_days is not None else None,
        last_scan_at=(
            _iso(now - timedelta(days=last_scan_days_ago))
            if last_scan_days_ago is not None
            else None
        ),
        last_scan_location=(last_scan_location or "Hub Bandung") if shipped else None,
        tracking_events=events,
        created_at=_iso(created),
    )


def build_orders(now: datetime) -> list[Order]:
    """Demo orders ORD-1001..1008 for Rani (CUST-0001), dates relative to ``now``."""
    transit, delivered = OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED
    return [
        # Skenario A: terlambat 2 hari, scan terakhir kemarin.
        _order(now, "ORD-1001", "Sepatu lari", 189_000, transit,
               shipped_days_ago=5, eta_days=-2, last_scan_days_ago=1),
        # Skenario B: tanpa pembaruan tracking 6 hari (>Rp100.000 -> approval).
        _order(now, "ORD-1002", "Jaket hujan", 349_000, transit,
               shipped_days_ago=8, eta_days=-4, last_scan_days_ago=6),
        # Skenario C: tercatat delivered 2 hari lalu (eskalasi).
        _order(now, "ORD-1003", "Headphone", 259_000, delivered,
               shipped_days_ago=5, eta_days=-2, last_scan_days_ago=2,
               last_scan_location="Bandung"),
        _order(now, "ORD-1004", "Kaos polos", 120_000, transit,
               shipped_days_ago=1, eta_days=2, last_scan_days_ago=0.5),
        _order(now, "ORD-1005", "Botol minum", 75_000, transit,
               shipped_days_ago=4, eta_days=-1, last_scan_days_ago=1),
        # Auto-refund (<= Rp100.000) karena tanpa pembaruan 6 hari.
        _order(now, "ORD-1006", "Casing ponsel", 85_000, transit,
               shipped_days_ago=8, eta_days=-4, last_scan_days_ago=6),
        _order(now, "ORD-1007", "Tas selempang", 150_000, OrderStatus.PROCESSING,
               shipped_days_ago=None, eta_days=4, last_scan_days_ago=None),
        _order(now, "ORD-1008", "Buku catatan", 99_000, delivered,
               shipped_days_ago=6, eta_days=-3, last_scan_days_ago=3,
               last_scan_location="Bandung"),
    ]  # fmt: skip


_SUMMARIES: dict[CaseCategory, str] = {
    CaseCategory.LATE_DELIVERY: "Pesanan terlambat; pelanggan menerima pengiriman ulang.",
    CaseCategory.LOST_PACKAGE: "Paket tanpa pembaruan tracking; refund diproses.",
    CaseCategory.NOT_RECEIVED: "Pelanggan melaporkan paket tidak diterima.",
    CaseCategory.STATUS_INQUIRY: "Pelanggan menanyakan status pesanan.",
    CaseCategory.ADDRESS_CHANGE: "Pelanggan meminta perubahan alamat.",
}


def _cases(now: datetime) -> list[Case]:
    """~25 resolved synthetic cases over the last 7 days (synthetic customers only)."""
    rng = random.Random(_RNG_SEED)
    customers = ["CUST-0002", "CUST-0003", "CUST-0004", "CUST-0005"]
    channels = [Channel.WHATSAPP, Channel.WHATSAPP, Channel.SMS, Channel.EMAIL]
    categories = list(_SUMMARIES)
    cases: list[Case] = []
    for i in range(1, SEEDED_CASE_COUNT + 1):
        category = categories[i % len(categories)]
        # ~70% auto_resolved, sisanya approved_by_staff / escalated.
        roll = i % 10
        if roll < 7:
            resolution_type = ResolutionType.AUTO_RESOLVED
        elif roll < 9:
            resolution_type = ResolutionType.APPROVED_BY_STAFF
        else:
            resolution_type = ResolutionType.ESCALATED
        inbound = now - timedelta(days=rng.uniform(0.2, 7.0))
        first_response = inbound + timedelta(milliseconds=rng.randint(4_000, 18_000))
        resolved = first_response + timedelta(minutes=rng.randint(2, 45))
        amount_idr = (
            rng.choice([85_000, 149_000, 189_000, 349_000])
            if category is CaseCategory.LOST_PACKAGE
            else None
        )
        action = {
            ResolutionType.AUTO_RESOLVED: "auto_resolution",
            ResolutionType.APPROVED_BY_STAFF: "refund",
            ResolutionType.ESCALATED: "escalate",
        }[resolution_type]
        cases.append(
            Case(
                case_id=f"CASE-SEED-{i:04d}",
                customer_id=customers[i % len(customers)],
                channel=channels[i % len(channels)],
                status=CaseStatus.RESOLVED,
                category=category,
                resolution_type=resolution_type,
                resolution=CaseResolution(
                    action=action,
                    amount_idr=amount_idr,
                    summary=_SUMMARIES[category],
                ),
                summary=_SUMMARIES[category],
                first_inbound_at=_iso(inbound),
                first_response_at=_iso(first_response),
                resolved_at=_iso(resolved),
                created_at=_iso(inbound),
                updated_at=_iso(resolved),
                seeded=True,
            )
        )
    return cases


def build_seed_data(now: datetime, phone_e164: str, email: str) -> SeedData:
    """Build every seed record relative to ``now`` (pure; no AWS calls)."""
    return SeedData(
        customers=_customers(now, phone_e164, email),
        orders=build_orders(now),
        cases=_cases(now),
    )


def seed(repos: Repositories, data: SeedData) -> dict[str, int]:
    """Write seed data with overwrite semantics; returns per-table record counts."""
    for customer in data.customers:
        repos.customers.put(customer)
    for order in data.orders:
        repos.orders.put(order)
    for case in data.cases:
        repos.cases.put(case)
    return {
        "customers": len(data.customers),
        "orders": len(data.orders),
        "cases": len(data.cases),
    }
