"""Deterministic resolution-notice templates (MSG-006, ``05-messaging.md`` §5).

Renders the final case-resolution notice per channel in Bahasa Indonesia. Parameters:
``case_id``, ``customer_name``, ``summary``, ``next_steps`` and optional
``voucher_code``. Only the final notice is templated; conversational turns are written
by the agent via ``send_message``.

Channel limits:
  - WhatsApp: <=600 chars.
  - SMS: <=160 chars where possible (single segment); the renderer truncates to fit.
  - Email: subject ``[ResolveAI] Kasus <case_id> telah diselesaikan`` + HTML card and a
    plain-text alternative.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

__all__ = [
    "WHATSAPP_MAX_CHARS",
    "SMS_MAX_CHARS",
    "EmailContent",
    "render_whatsapp",
    "render_sms",
    "render_email_subject",
    "render_email",
]

WHATSAPP_MAX_CHARS = 600
SMS_MAX_CHARS = 160


def render_whatsapp(
    *,
    case_id: str,
    customer_name: str,
    summary: str,
    next_steps: str,
    voucher_code: str | None = None,
) -> str:
    """Render the WhatsApp resolution notice (<=600 chars).

    Raises:
        ValueError: if the rendered message exceeds ``WHATSAPP_MAX_CHARS``. The body is
        short by construction, so this guards against pathologically long parameters
        rather than silently truncating a WhatsApp message.
    """
    lines = [
        f"Halo {customer_name},",
        "",
        summary,
        "",
        f"Langkah berikutnya: {next_steps}",
    ]
    if voucher_code:
        lines.append(f"Kode voucher: {voucher_code}")
    lines.append(f"Kode kasus: {case_id}")
    message = "\n".join(lines)

    if len(message) > WHATSAPP_MAX_CHARS:
        raise ValueError(f"whatsapp message is {len(message)} chars, exceeds {WHATSAPP_MAX_CHARS}")
    return message


def render_sms(
    *,
    case_id: str,
    customer_name: str,
    summary: str,
    next_steps: str,
    voucher_code: str | None = None,
) -> str:
    """Render a single-sentence SMS notice, truncated to fit ``SMS_MAX_CHARS``.

    Unused parameters (``customer_name``, ``next_steps``) are accepted to keep a uniform
    renderer signature across channels; SMS keeps only the summary plus the case code to
    stay within one segment.
    """
    del customer_name, next_steps  # intentionally unused for the single-segment SMS
    suffix = f" (Kasus {case_id})"
    voucher_part = f" Voucher: {voucher_code}." if voucher_code else ""
    budget = SMS_MAX_CHARS - len(suffix) - len(voucher_part)

    body = summary.strip()
    if len(body) > budget:
        # Reserve one char for an ellipsis so the result stays <= budget.
        body = body[: max(budget - 1, 0)].rstrip() + "…"

    return f"{body}{voucher_part}{suffix}"


def render_email_subject(case_id: str) -> str:
    """Render the fixed email subject line."""
    return f"[ResolveAI] Kasus {case_id} telah diselesaikan"


@dataclass(frozen=True)
class EmailContent:
    """Rendered email: subject plus HTML and plain-text bodies."""

    subject: str
    html: str
    text: str


def render_email(
    *,
    case_id: str,
    customer_name: str,
    summary: str,
    next_steps: str,
    voucher_code: str | None = None,
) -> EmailContent:
    """Render the email resolution notice (HTML card + text alternative).

    All interpolated values are HTML-escaped in the HTML body to avoid injection.
    """
    subject = render_email_subject(case_id)

    voucher_html = (
        f"<p><strong>Voucher:</strong> {escape(voucher_code)}</p>" if voucher_code else ""
    )
    html = (
        '<div style="font-family:sans-serif;max-width:480px">'
        f"<h2>Halo {escape(customer_name)},</h2>"
        f"<p>{escape(summary)}</p>"
        "<hr>"
        f"<p><strong>Kode kasus:</strong> {escape(case_id)}</p>"
        f"<p><strong>Langkah berikutnya:</strong> {escape(next_steps)}</p>"
        f"{voucher_html}"
        "</div>"
    )

    text_lines = [
        f"Halo {customer_name},",
        "",
        summary,
        "",
        f"Kode kasus: {case_id}",
        f"Langkah berikutnya: {next_steps}",
    ]
    if voucher_code:
        text_lines.append(f"Voucher: {voucher_code}")
    text = "\n".join(text_lines)

    return EmailContent(subject=subject, html=html, text=text)
