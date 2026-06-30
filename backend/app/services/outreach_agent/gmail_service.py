"""
PATHS Backend — Gmail send service (HR-user OAuth).

Sends RFC-822-formatted MIME emails through the Gmail API
``users.messages.send`` endpoint, authenticated with the HR's per-user
access token.

Plain-text bodies are wrapped as ``text/plain``. The caller is responsible
for substituting the scheduling link before calling ``send_email``.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.services.outreach_agent.google_oauth_service import (
    get_access_token,
    get_user_email,
)

logger = logging.getLogger(__name__)


_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


@dataclass
class GmailSendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


def send_email(
    db: Session,
    *,
    hr_user_id: UUID,
    to: str,
    subject: str,
    body: str,
    cc: list[str] | None = None,
) -> GmailSendResult:
    if not to:
        return GmailSendResult(success=False, error="missing_recipient")
    token = get_access_token(db, user_id=hr_user_id)
    if not token:
        return GmailSendResult(success=False, error="google_not_connected")
    sender = get_user_email(db, user_id=hr_user_id)

    msg = MIMEText(body or "", _charset="utf-8")
    msg["To"] = to
    msg["Subject"] = subject or "(no subject)"
    if sender:
        msg["From"] = sender
    if cc:
        msg["Cc"] = ", ".join([c for c in cc if c])

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload = {"raw": raw}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                _GMAIL_SEND_URL,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        return GmailSendResult(success=False, error=f"gmail_http_error:{exc}")
    if r.status_code >= 400:
        return GmailSendResult(
            success=False, error=f"gmail_send_failed:{r.text[:400]}",
        )
    data = r.json() or {}
    return GmailSendResult(success=True, message_id=data.get("id"), raw=data)


__all__ = ["GmailSendResult", "send_email"]
