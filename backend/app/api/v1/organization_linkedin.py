"""
PATHS Backend — Organization LinkedIn account endpoints (fix6.md follow-up).

Routes (mounted under /api/v1):

  GET    /organizations/{org_id}/linkedin-account     read connection state
  POST   /organizations/{org_id}/linkedin-account     connect / update
  DELETE /organizations/{org_id}/linkedin-account     disconnect

A POST saves the recruiter's ``li_at`` (and optional ``JSESSIONID``) on the
``organizations`` row, encrypts both, and writes
``~/.linkedin-mcp/cookies.json`` so the linkedin-mcp-server's
``LinkedInBrowser.import_cookies`` picks them up on its next browser
context creation. The plaintext cookies never leave this process — the
GET endpoint only echoes whether a connection exists.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.organization import Organization
from app.services.source_candidate.linkedin_account import (
    apply_org_credentials_to_mcp,
    clear_credentials_on_org,
    clear_mcp_cookies,
    cookies_json_path,
    store_credentials_on_org,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Organization LinkedIn Account"])


# ── Schemas ──────────────────────────────────────────────────────────────


class LinkedInAccountState(BaseModel):
    connected: bool
    email: Optional[str] = None
    connected_at: Optional[datetime] = None
    has_jsessionid: bool = False
    cookies_file_path: str
    cookies_file_present: bool


class LinkedInAccountIn(BaseModel):
    email: Optional[str] = Field(default=None, max_length=255)
    li_at: str = Field(min_length=10, max_length=2048)
    jsessionid: Optional[str] = Field(default=None, max_length=512)


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize(org: Organization) -> LinkedInAccountState:
    path = cookies_json_path()
    return LinkedInAccountState(
        connected=bool(org.linkedin_li_at_encrypted),
        email=org.linkedin_account_email,
        connected_at=org.linkedin_connected_at,
        has_jsessionid=bool(org.linkedin_jsessionid_encrypted),
        cookies_file_path=str(path),
        cookies_file_present=path.exists(),
    )


def _load_org(db: Session, org_id: UUID, ctx: OrgContext) -> Organization:
    if org_id != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own organisation's LinkedIn account.",
        )
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return org


# ── Routes ───────────────────────────────────────────────────────────────


@router.get(
    "/organizations/{organization_id}/linkedin-account",
    response_model=LinkedInAccountState,
)
def get_linkedin_account(
    organization_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> LinkedInAccountState:
    return _serialize(_load_org(db, organization_id, ctx))


@router.post(
    "/organizations/{organization_id}/linkedin-account",
    response_model=LinkedInAccountState,
    status_code=status.HTTP_200_OK,
)
def connect_linkedin_account(
    organization_id: UUID,
    body: LinkedInAccountIn,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> LinkedInAccountState:
    org = _load_org(db, organization_id, ctx)
    store_credentials_on_org(
        org,
        email=body.email,
        li_at=body.li_at,
        jsessionid=body.jsessionid,
        connected_by_user_id=ctx.user.id,
    )
    db.commit()
    db.refresh(org)
    # Best-effort: write cookies.json now so the MCP server can pick them
    # up immediately. Failures don't undo the DB write because we can
    # always reapply on backend startup.
    try:
        apply_org_credentials_to_mcp(org)
    except Exception:  # noqa: BLE001
        logger.exception(
            "[LinkedInAccount] failed to write MCP cookies; "
            "credentials still saved in DB and can be re-applied",
        )
    return _serialize(org)


@router.delete(
    "/organizations/{organization_id}/linkedin-account",
    response_model=LinkedInAccountState,
)
def disconnect_linkedin_account(
    organization_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> LinkedInAccountState:
    org = _load_org(db, organization_id, ctx)
    clear_credentials_on_org(org)
    db.commit()
    db.refresh(org)
    try:
        clear_mcp_cookies()
    except Exception:  # noqa: BLE001
        logger.exception("[LinkedInAccount] failed to remove MCP cookies file")
    return _serialize(org)
