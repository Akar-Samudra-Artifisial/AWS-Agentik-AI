#!/usr/bin/env python3
"""Manual messaging smoke test (MSG-010).

Sends ONE real message through the AWS SDK on the chosen channel, for manual testing
and judge evidence (PRD 05 §5a). This is not a mock: it calls the same adapters the
agent uses at runtime. Origination identities come from the environment
(``SES_FROM_EMAIL``, ``SMS_ORIGINATION_IDENTITY``, ``WA_PHONE_NUMBER_ID``); AWS
credentials/region are resolved by boto3's standard chain.

Examples:
    python scripts/send_test_message.py --channel email --to you@example.com
    python scripts/send_test_message.py --channel sms --to +6281234567890
    python scripts/send_test_message.py --channel whatsapp --to +6281234567890 \\
        --text "Halo dari ResolveAI"
"""

from __future__ import annotations

import argparse
import sys

from resolveai_common.logging import configure_root_logger, get_logger
from resolveai_common.messaging.dispatch import send_on_channel
from resolveai_common.messaging.types import SendResult
from resolveai_common.models import Channel
from resolveai_common.phone import normalize_phone

_DEFAULT_TEXT = "Pesan uji dari ResolveAI (send_test_message.py)."
_DEFAULT_SUBJECT = "[ResolveAI] Pesan uji"

logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="send_test_message.py",
        description="Send one real test message via WhatsApp, SMS, or email.",
    )
    parser.add_argument(
        "--channel",
        required=True,
        choices=[c.value for c in Channel],
        help="Channel to send on.",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient: E.164 phone for whatsapp/sms, email address for email.",
    )
    parser.add_argument(
        "--text",
        default=_DEFAULT_TEXT,
        help="Message body (plain text).",
    )
    parser.add_argument(
        "--subject",
        default=_DEFAULT_SUBJECT,
        help="Email subject (email channel only).",
    )
    return parser.parse_args(argv)


def _send(channel: Channel, to: str, text: str, subject: str) -> SendResult:
    """Route the send, validating the recipient for the chosen channel."""
    if channel is Channel.EMAIL:
        if "@" not in to:
            raise ValueError(f"email channel needs an email address, got: {to!r}")
        return send_on_channel(channel, text=text, to_email=to, subject=subject)

    normalized = normalize_phone(to)
    if normalized is None:
        raise ValueError(f"invalid phone number for {channel.value}: {to!r}")
    return send_on_channel(channel, text=text, to_e164=normalized)


def main(argv: list[str] | None = None) -> int:
    configure_root_logger()
    args = _parse_args(argv)
    channel = Channel(args.channel)

    try:
        result = _send(channel, args.to, args.text, args.subject)
    except ValueError as exc:
        logger.error("send_test_message invalid input: %s", exc)
        return 2

    if result.ok:
        logger.info(
            "send_test_message sent",
            extra={
                "channel": result.channel.value,
                "provider_message_id": result.provider_message_id,
            },
        )
        return 0

    logger.error(
        "send_test_message failed",
        extra={"channel": result.channel.value, "error": result.error},
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
