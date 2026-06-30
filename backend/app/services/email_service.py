"""PATHS Backend — shared email sending service.

Thin wrapper around ``smtplib`` that reuses the existing ``settings.smtp_*``
configuration so we don't have two competing senders. When SMTP is not
configured (dev / preview), the helper falls back to logging the message
at INFO level so HR can still copy credentials out of the server logs
during local development.

All email functions return a dict ``{ok: bool, provider: str, error?: str}``.
They NEVER raise — sending failure must not block the inviting workflow.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_username)


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> dict[str, Any]:
    """Send a plain-text (and optionally HTML) email via SMTP.

    Falls back to a dev-mode logger when SMTP isn't configured.
    """
    if not to or "@" not in to:
        return {"ok": False, "provider": "none", "error": "invalid_recipient"}

    if not _smtp_configured():
        logger.info(
            "[email_service] SMTP not configured — would have sent\n"
            "  To:      %s\n"
            "  Subject: %s\n"
            "  Body:\n%s",
            to, subject, body,
        )
        return {"ok": True, "provider": "logger"}

    msg: Any
    if html:
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")

    msg["Subject"] = subject
    msg["From"] = settings.outreach_from_email or settings.smtp_username
    msg["To"] = to

    try:
        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port)) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return {"ok": True, "provider": "smtp"}
    except Exception as exc:  # noqa: BLE001
        # NEVER log the password or full body; just enough to diagnose.
        logger.warning(
            "[email_service] SMTP send failed to %s subject=%r: %s",
            to, subject, str(exc)[:200],
        )
        return {"ok": False, "provider": "smtp", "error": str(exc)[:200]}


# ── Invitation email helper (fix8&9 Update 2) ───────────────────────────────


def compose_organization_invite_email(
    *,
    to: str,
    invited_member_name: str,
    inviter_name: str,
    organization_name: str,
    temporary_password: str,
    inviter_email: str | None = None,
    login_url: str | None = None,
) -> dict[str, str]:
    """Build the invitation email WITHOUT sending it.

    Used by the preview-and-approve flow (the admin sees the exact recipient
    address, subject and body before anything is sent) and by the actual
    send. The invitation is written in the organisation's name and identifies
    the inviter by full name and email address.
    """
    inviter_line = (
        f"{inviter_name} ({inviter_email})" if inviter_email else inviter_name
    )
    subject = f"{inviter_name} invited you to join {organization_name} on PATHS"
    login_line = f"Login URL: {login_url}\n\n" if login_url else ""
    body = (
        f"Hello {invited_member_name},\n\n"
        f"You now have an account on PATHS.\n\n"
        f"{inviter_line} has invited you to join the organization account of "
        f"{organization_name}.\n\n"
        f"You can log in using the following temporary credentials:\n\n"
        f"Email: {to}\n"
        f"Temporary Password: {temporary_password}\n\n"
        f"{login_line}"
        f"After logging in, please change your password.\n\n"
        f"Best regards,\n"
        f"The {organization_name} Team\n"
        f"(sent on behalf of {organization_name} via PATHS)\n"
    )
    return {"to": to, "subject": subject, "body": body}


def send_organization_invite_email(
    *,
    to: str,
    invited_member_name: str,
    inviter_name: str,
    organization_name: str,
    temporary_password: str,
    inviter_email: str | None = None,
    login_url: str | None = None,
) -> dict[str, Any]:
    """Send the invitation email with login credentials."""
    composed = compose_organization_invite_email(
        to=to,
        invited_member_name=invited_member_name,
        inviter_name=inviter_name,
        organization_name=organization_name,
        temporary_password=temporary_password,
        inviter_email=inviter_email,
        login_url=login_url,
    )
    return send_email(
        to=composed["to"], subject=composed["subject"], body=composed["body"],
    )
