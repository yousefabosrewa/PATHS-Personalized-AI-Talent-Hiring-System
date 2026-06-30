"""
PATHS Backend — Google integration endpoints (OAuth 2.0).

Routes:
  GET  /api/v1/google-integration/connect   — return authorize URL
  GET  /api/v1/google-integration/callback  — OAuth redirect target
  GET  /api/v1/google-integration/status    — current HR connection state
  POST /api/v1/google-integration/disconnect — revoke local tokens
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_active_user,
    get_current_hiring_org_context,
)
from app.db.models.user import User
from app.schemas.outreach_agent import (
    GoogleConnectResponse,
    GoogleStatusResponse,
)
from app.services.outreach_agent.google_oauth_service import (
    GoogleOAuthError,
    build_authorize_url,
    disconnect,
    exchange_code,
    get_status,
    is_configured,
)

logger = logging.getLogger(__name__)
settings = get_settings()


router = APIRouter(
    prefix="/google-integration",
    tags=["Google Integration"],
)


@router.get("/connect", response_model=GoogleConnectResponse)
def connect(
    user: User = Depends(get_current_active_user),
):
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI.",
        )
    try:
        url = build_authorize_url(user_id=user.id)
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GoogleConnectResponse(authorize_url=url)


@router.get("/callback", include_in_schema=False)
def callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """OAuth redirect target. Exchanges the code, then renders a tiny HTML
    page that closes the popup and posts a message to the opener."""
    if error:
        return _render_callback_html(success=False, message=error)
    if not code or not state:
        return _render_callback_html(success=False, message="missing code or state")
    try:
        result = exchange_code(db, code=code, state=state)
    except GoogleOAuthError as exc:
        return _render_callback_html(success=False, message=str(exc))
    return _render_callback_html(success=True, message=result.email or "connected")


@router.get("/status", response_model=GoogleStatusResponse)
def status_endpoint(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    s = get_status(db, user_id=user.id)
    return GoogleStatusResponse(
        connected=s.connected,
        configured=is_configured(),
        email=s.email,
        expires_at=s.expires_at,
        scopes=s.scopes,
        last_error=s.last_error,
    )


@router.post("/disconnect", status_code=204, response_class=Response)
def disconnect_endpoint(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    disconnect(db, user_id=user.id)
    db.commit()
    return Response(status_code=204)


# ── Internal HTML callback (auto-closes popup) ───────────────────────────


def _render_callback_html(*, success: bool, message: str) -> HTMLResponse:
    color = "#10b981" if success else "#f43f5e"
    label = "Google connected" if success else "Connection failed"
    safe_msg = (message or "").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{label}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;background:#0b0b10;color:#e5e7eb;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}.card{{padding:24px 28px;border:1px solid #20212b;background:#111218;border-radius:12px;text-align:center;max-width:380px}}.dot{{display:inline-block;width:10px;height:10px;border-radius:999px;background:{color};margin-right:8px;vertical-align:middle}}h1{{font-size:16px;margin:0 0 8px}}p{{margin:0;font-size:13px;color:#9ca3af}}</style>
</head><body>
<div class='card'><h1><span class='dot'></span>{label}</h1><p>{safe_msg}</p>
<p style='margin-top:8px;color:#6b7280'>You can close this window.</p></div>
<script>
try {{
  if (window.opener) {{
    window.opener.postMessage({{type:'paths-google-oauth',success:{str(success).lower()},message:{repr(message)}}}, '*');
  }}
}} catch (e) {{}}
setTimeout(() => {{ try {{ window.close(); }} catch (e) {{}} }}, 1200);
</script></body></html>"""
    return HTMLResponse(html)
