"""
PATHS Backend — Google OAuth 2.0 service for HR users.

Stores per-HR-user access + refresh tokens (encrypted via ``token_crypto``).
Never logs or returns the raw secrets to the frontend.

Compliant flow:
  GET  /api/v1/google-integration/connect  -> 302 to Google consent screen
  GET  /api/v1/google-integration/callback -> exchanges code, persists tokens
  GET  /api/v1/google-integration/status   -> { connected, email, expires_at }

If Google credentials are not configured, the connect URL falls back to a
local error page so the rest of the app continues to work; the Outreach UI
shows a "Connect Google Calendar and Gmail to send outreach" notice.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.outreach_agent import GoogleIntegration
from app.services.outreach_agent.token_crypto import (
    constant_time_eq,
    decrypt_secret,
    encrypt_secret,
)

logger = logging.getLogger(__name__)
settings = get_settings()


_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass
class GoogleConnectionStatus:
    connected: bool
    email: str | None
    expires_at: datetime | None
    scopes: list[str]
    last_error: str | None = None


class GoogleOAuthError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri,
    )


def build_authorize_url(*, user_id: UUID, state_extra: str | None = None) -> str:
    """Return the Google consent-screen URL for this HR user."""
    if not is_configured():
        raise GoogleOAuthError("google_oauth_not_configured")
    state = _encode_state(user_id=user_id, nonce=str(int(time.time())), extra=state_extra)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_resolved_scopes()),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def parse_state(state: str) -> dict[str, Any]:
    return _decode_state(state)


def exchange_code(db: Session, *, code: str, state: str) -> GoogleConnectionStatus:
    if not is_configured():
        raise GoogleOAuthError("google_oauth_not_configured")
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_redirect_uri,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(_TOKEN_URL, data=payload)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"token_exchange_http_error: {exc}") from exc
    if r.status_code >= 400:
        raise GoogleOAuthError(f"token_exchange_failed: {r.text[:300]}")
    tokens = r.json()
    info = parse_state(state)
    user_id = UUID(str(info["user_id"]))
    return _persist_tokens(db, user_id=user_id, tokens=tokens)


def get_status(db: Session, *, user_id: UUID) -> GoogleConnectionStatus:
    integ = db.execute(
        select(GoogleIntegration).where(GoogleIntegration.user_id == user_id)
    ).scalar_one_or_none()
    if integ is None:
        return GoogleConnectionStatus(
            connected=False, email=None, expires_at=None, scopes=[],
        )
    return GoogleConnectionStatus(
        connected=integ.status == "connected"
        and bool(integ.refresh_token_encrypted or integ.access_token_encrypted),
        email=integ.google_email,
        expires_at=integ.token_expiry,
        scopes=(integ.scopes or "").split() if integ.scopes else [],
        last_error=integ.last_error,
    )


def disconnect(db: Session, *, user_id: UUID) -> None:
    integ = db.execute(
        select(GoogleIntegration).where(GoogleIntegration.user_id == user_id)
    ).scalar_one_or_none()
    if integ is None:
        return
    integ.access_token_encrypted = None
    integ.refresh_token_encrypted = None
    integ.token_expiry = None
    integ.status = "disconnected"
    integ.last_error = None
    db.flush()


def get_access_token(db: Session, *, user_id: UUID) -> str | None:
    """Return a fresh access token (refreshing if needed). None if not connected."""
    integ = db.execute(
        select(GoogleIntegration).where(GoogleIntegration.user_id == user_id)
    ).scalar_one_or_none()
    if integ is None or not (integ.access_token_encrypted or integ.refresh_token_encrypted):
        return None

    now = datetime.now(timezone.utc)
    not_expired = (
        integ.token_expiry is not None
        and integ.token_expiry > now + timedelta(seconds=30)
    )
    if integ.access_token_encrypted and not_expired:
        return decrypt_secret(integ.access_token_encrypted)

    refresh_token = decrypt_secret(integ.refresh_token_encrypted)
    if not refresh_token or not is_configured():
        return decrypt_secret(integ.access_token_encrypted)

    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(_TOKEN_URL, data=payload)
    except httpx.HTTPError as exc:
        integ.last_error = f"refresh_http_error:{exc}"[:500]
        db.flush()
        return decrypt_secret(integ.access_token_encrypted)
    if r.status_code >= 400:
        integ.last_error = f"refresh_failed:{r.text[:300]}"
        integ.status = "needs_reauth"
        db.flush()
        return None

    tokens = r.json()
    new_access = tokens.get("access_token")
    if not new_access:
        return decrypt_secret(integ.access_token_encrypted)
    expires_in = int(tokens.get("expires_in", 3600))
    integ.access_token_encrypted = encrypt_secret(new_access)
    integ.token_expiry = now + timedelta(seconds=expires_in)
    integ.last_error = None
    integ.status = "connected"
    db.flush()
    return new_access


def get_user_email(db: Session, *, user_id: UUID) -> str | None:
    integ = db.execute(
        select(GoogleIntegration).where(GoogleIntegration.user_id == user_id)
    ).scalar_one_or_none()
    return integ.google_email if integ else None


# ── Internal helpers ─────────────────────────────────────────────────────


def _resolved_scopes() -> list[str]:
    raw = (settings.google_scopes or "").strip()
    if not raw:
        return [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.freebusy",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ]
    return [s for s in raw.replace(",", " ").split() if s]


def _persist_tokens(
    db: Session, *, user_id: UUID, tokens: dict[str, Any],
) -> GoogleConnectionStatus:
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 3600))
    scopes = tokens.get("scope", " ".join(_resolved_scopes()))

    email = None
    if access:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access}"},
                )
                if resp.status_code == 200:
                    email = (resp.json() or {}).get("email")
        except httpx.HTTPError:
            pass

    integ = db.execute(
        select(GoogleIntegration).where(GoogleIntegration.user_id == user_id)
    ).scalar_one_or_none()
    if integ is None:
        integ = GoogleIntegration(user_id=user_id)
        db.add(integ)

    integ.access_token_encrypted = encrypt_secret(access) if access else integ.access_token_encrypted
    if refresh:
        integ.refresh_token_encrypted = encrypt_secret(refresh)
    integ.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    integ.scopes = scopes
    integ.status = "connected"
    integ.last_error = None
    if email:
        integ.google_email = email
    db.flush()
    db.commit()
    return GoogleConnectionStatus(
        connected=True,
        email=integ.google_email,
        expires_at=integ.token_expiry,
        scopes=(integ.scopes or "").split() if integ.scopes else [],
    )


def _encode_state(*, user_id: UUID, nonce: str, extra: str | None) -> str:
    payload = {"u": str(user_id), "n": nonce, "x": extra or ""}
    return _b64url(json.dumps(payload).encode("utf-8"))


def _decode_state(state: str) -> dict[str, Any]:
    try:
        raw = _b64url_decode(state).decode("utf-8")
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise GoogleOAuthError(f"invalid_state:{exc}") from exc
    if "u" not in payload:
        raise GoogleOAuthError("invalid_state:missing_user")
    return {"user_id": payload["u"], "nonce": payload.get("n"), "extra": payload.get("x")}


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    import base64

    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


__all__ = [
    "GoogleConnectionStatus",
    "GoogleOAuthError",
    "build_authorize_url",
    "disconnect",
    "exchange_code",
    "get_access_token",
    "get_status",
    "get_user_email",
    "is_configured",
    "parse_state",
]
