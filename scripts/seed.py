#!/usr/bin/env python3
"""Seed synthetic demo data into DynamoDB (PRD 07 §3, TST-001).

Idempotent: every record has a fixed ID and is written with ``put_item`` (overwrite), so
re-running refreshes timestamps instead of creating duplicates. All dates are relative to
"now" at seed time (UTC ISO 8601). Money is integer rupiah. The record builders live in
``resolveai_common.seed_data`` (shared with ``POST /api/demo/reset``).

The demo customer's contact comes from ``DEMO_PHONE_E164`` / ``DEMO_EMAIL`` (never
hardcoded). Synthetic customers CUST-0002..0005 use fictitious contacts and are the only
owners of the seeded case history, so seeding never causes a message to be sent.

Table names are ``<prefix>-<table>`` with prefix from ``--prefix`` or
``RESOLVEAI_TABLE_PREFIX`` (default ``resolveai-dev``). AWS credentials/region are
resolved by boto3's standard chain.

Example:
    DEMO_PHONE_E164=+6281234567890 DEMO_EMAIL=you@example.com python scripts/seed.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

from resolveai_common.logging import configure_root_logger, get_logger
from resolveai_common.phone import normalize_phone
from resolveai_common.repository import Repositories
from resolveai_common.seed_data import (
    SEEDED_CASE_COUNT,
    SeedData,
    build_seed_data,
    seed,
)

__all__ = [
    "SEEDED_CASE_COUNT",
    "SeedConfigError",
    "SeedData",
    "build_seed_data",
    "load_demo_contact",
    "main",
    "seed",
]

logger = get_logger(__name__)


class SeedConfigError(ValueError):
    """Raised when required seed configuration (demo contact env vars) is missing/invalid."""


def load_demo_contact(env: dict[str, str] | None = None) -> tuple[str, str]:
    """Read and validate the demo contact from ``DEMO_PHONE_E164`` and ``DEMO_EMAIL``."""
    source = os.environ if env is None else env
    raw_phone = source.get("DEMO_PHONE_E164", "").strip()
    email = source.get("DEMO_EMAIL", "").strip()
    missing = [
        name
        for name, value in (("DEMO_PHONE_E164", raw_phone), ("DEMO_EMAIL", email))
        if not value
    ]
    if missing:
        raise SeedConfigError(
            f"env {', '.join(missing)} kosong: isi kontak demo developer sebelum seed "
            "(mis. DEMO_PHONE_E164=+62812..., DEMO_EMAIL=nama@domain)"
        )
    phone = normalize_phone(raw_phone)
    if phone is None:
        raise SeedConfigError(
            f"DEMO_PHONE_E164 bukan nomor telepon valid: {raw_phone!r}"
        )
    if "@" not in email:
        raise SeedConfigError(f"DEMO_EMAIL bukan alamat email valid: {email!r}")
    return phone, email


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed.py", description="Seed synthetic ResolveAI demo data into DynamoDB."
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Table name prefix (default: RESOLVEAI_TABLE_PREFIX or resolveai-dev).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_root_logger()
    args = _parse_args(argv)
    try:
        phone, email = load_demo_contact()
    except SeedConfigError as exc:
        logger.error("seed config invalid: %s", exc)
        print(f"seed: {exc}", file=sys.stderr)
        return 2

    data = build_seed_data(datetime.now(UTC), phone, email)
    counts = seed(Repositories(prefix=args.prefix), data)
    logger.info("seed completed", extra=counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
