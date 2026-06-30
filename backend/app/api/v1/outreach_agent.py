"""
PATHS Backend — Outreach Agent endpoints (HR-side, authenticated).

The flow is intentionally simple:

  1. POST /outreach/generate-email      — LLM-drafts subject + body
  2. POST /outreach/save-draft          — persists the session in draft
                                          status and returns the booking_link
  3. POST /outreach/send                — creates the session (or re-uses an
                                          existing draft) and sends via Gmail
                                          atomically. The raw scheduling token
                                          is generated server-side and never
                                          stored in plaintext.
  4. GET  /outreach/{candidate_id}/history

The token never round-trips through the DB in plaintext: every endpoint
that needs the booking link generates a new token and immediately uses it,
the SHA-256 hash being the only persistent reference.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.outreach_agent import OutreachSession
from app.schemas.outreach_agent import (
    CreateSessionRequest,
    CreateSessionResponse,
    GenerateEmailRequest,
    GeneratedEmailSchema,
    OutreachHistoryItem,
    OutreachHistoryResponse,
    SendSessionResponse,
)
from app.services.outreach_agent import outreach_service
from app.services.outreach_agent.outreach_service import CreateSessionInput

logger = logging.getLogger(__name__)
settings = get_settings()


router = APIRouter(prefix="/outreach", tags=["Outreach Agent"])


def _ensure_candidate_visible(
    db: Session, *, candidate_id: UUID, organization_id: UUID,
) -> Candidate:
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate_not_found")
    return cand


def _ensure_job_visible(
    db: Session, *, job_id: UUID | None, organization_id: UUID,
) -> Job | None:
    if job_id is None:
        return None
    job = db.get(Job, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


def _build_link(raw_token: str) -> str:
    base = settings.outreach_public_base_url.rstrip("/")
    return f"{base}/schedule/{raw_token}"


@router.post("/generate-email", response_model=GeneratedEmailSchema)
def generate_email(
    body: GenerateEmailRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    _ensure_candidate_visible(
        db, candidate_id=body.candidate_id, organization_id=ctx.organization_id,
    )
    _ensure_job_visible(
        db, job_id=body.job_id, organization_id=ctx.organization_id,
    )
    try:
        email = outreach_service.generate_email_for_candidate(
            db,
            candidate_id=body.candidate_id,
            job_id=body.job_id,
            organization_id=ctx.organization_id,
            hr_user_id=ctx.user.id,
            hr_name=ctx.user.full_name,
            interview_type=body.interview_type,
            is_final_offer=body.is_final_offer,
            extra_instructions=body.extra_instructions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratedEmailSchema(**email.to_dict())


# ── Complete-profile outreach ───────────────────────────────────────────
# Invites a sourced candidate to create their own account on PATHS and
# complete their profile. Unlike interview outreach there is NO booking link,
# NO HR availability, and no Google dependency — just a reviewed email.


class ProfileCompletionGenerateRequest(BaseModel):
    candidate_id: UUID


class ProfileCompletionEmailOut(BaseModel):
    subject: str
    body: str
    signup_url: str


class ProfileCompletionSendRequest(BaseModel):
    candidate_id: UUID
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    recipient_email: str | None = None


@router.post("/profile-completion/generate", response_model=ProfileCompletionEmailOut)
def generate_profile_completion_email(
    body: ProfileCompletionGenerateRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Draft the "create your account / complete your profile" email."""
    cand = _ensure_candidate_visible(
        db, candidate_id=body.candidate_id, organization_id=ctx.organization_id,
    )
    from app.db.models.organization import Organization

    org = db.get(Organization, ctx.organization_id)
    org_name = org.name if org else "our organization"
    hr_name = ctx.user.full_name or ctx.user.email
    base = settings.outreach_public_base_url.rstrip("/")
    signup_url = f"{base}/candidate-signup"
    first_name = (cand.full_name or "there").split(" ")[0]
    title_line = f" as {cand.current_title}" if cand.current_title else ""

    subject = f"{org_name} would like to know more about you — complete your profile on PATHS"
    email_body = (
        f"Hello {first_name},\n\n"
        f"My name is {hr_name} and I'm reaching out on behalf of {org_name}. "
        f"We came across your professional profile{title_line} and would love "
        f"to learn more about you.\n\n"
        f"To move forward, we invite you to create your own account on PATHS — "
        f"our hiring platform — and complete your profile (skills, experience, "
        f"CV). A complete profile lets our team match you accurately to the "
        f"right opportunities at {org_name}.\n\n"
        f"Create your account here: {signup_url}\n\n"
        f"It only takes a few minutes, and you stay in full control of your "
        f"information.\n\n"
        f"Best regards,\n"
        f"{hr_name}\n"
        f"{org_name} — via PATHS"
    )
    return ProfileCompletionEmailOut(subject=subject, body=email_body, signup_url=signup_url)


@router.post("/profile-completion/send")
def send_profile_completion_email(
    body: ProfileCompletionSendRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Send the reviewed complete-profile email (plain email — no booking
    link or calendar). Uses SMTP with the dev-logger fallback."""
    cand = _ensure_candidate_visible(
        db, candidate_id=body.candidate_id, organization_id=ctx.organization_id,
    )
    to = (body.recipient_email or cand.email or "").strip()
    if not to:
        raise HTTPException(status_code=400, detail="candidate_has_no_email")

    from app.services.email_service import send_email

    result = send_email(to=to, subject=body.subject.strip(), body=body.body)
    ok = bool(result.get("ok"))
    if not ok:
        raise HTTPException(
            status_code=502,
            detail=f"Email send failed: {result.get('error', 'unknown')}",
        )
    logger.info(
        "[outreach] profile-completion email sent to %s (provider=%s) by %s",
        to, result.get("provider"), ctx.user.email,
    )
    return {"ok": True, "provider": result.get("provider"), "recipient": to}


@router.post("/save-draft", response_model=CreateSessionResponse)
def save_draft(
    body: CreateSessionRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Persist a draft outreach session and return the candidate-facing
    booking link. HR can preview the link before clicking Send.
    """
    cand = _ensure_candidate_visible(
        db, candidate_id=body.candidate_id, organization_id=ctx.organization_id,
    )
    _ensure_job_visible(
        db, job_id=body.job_id, organization_id=ctx.organization_id,
    )
    if not (body.recipient_email or cand.email):
        raise HTTPException(status_code=400, detail="candidate_has_no_email")

    try:
        session, raw_token = outreach_service.create_session(
            db,
            body=CreateSessionInput(
                candidate_id=body.candidate_id,
                job_id=body.job_id,
                organization_id=ctx.organization_id,
                hr_user_id=ctx.user.id,
                subject=body.subject,
                email_body=body.email_body,
                interview_type=body.interview_type,
                duration_minutes=body.duration_minutes,
                buffer_minutes=body.buffer_minutes,
                timezone=body.timezone,
                expires_at=body.expires_at,
                availability=[w.model_dump() for w in body.availability],
                recipient_email=body.recipient_email,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CreateSessionResponse(
        session_id=session.id,
        status=session.status,
        booking_link=_build_link(raw_token),
        expires_at=session.expires_at,
    )


@router.post("/send", response_model=SendSessionResponse)
def send_atomic(
    body: CreateSessionRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Create + send in one atomic call.

    HR clicks **Send Outreach** in the modal; the backend creates the
    session, replaces ``{{SCHEDULING_LINK}}`` with the freshly generated
    URL, and sends via Gmail. The raw token is only kept in memory for
    the duration of the request — only the SHA-256 hash is persisted.
    """
    cand = _ensure_candidate_visible(
        db, candidate_id=body.candidate_id, organization_id=ctx.organization_id,
    )
    _ensure_job_visible(
        db, job_id=body.job_id, organization_id=ctx.organization_id,
    )
    if not (body.recipient_email or cand.email):
        raise HTTPException(status_code=400, detail="candidate_has_no_email")

    # Pre-flight Google check so we fail fast with a clear message.
    from app.services.outreach_agent.google_oauth_service import get_status

    s = get_status(db, user_id=ctx.user.id)
    if not s.connected:
        raise HTTPException(
            status_code=400,
            detail="Connect Google Calendar and Gmail to send outreach.",
        )

    try:
        session, raw_token = outreach_service.create_session(
            db,
            body=CreateSessionInput(
                candidate_id=body.candidate_id,
                job_id=body.job_id,
                organization_id=ctx.organization_id,
                hr_user_id=ctx.user.id,
                subject=body.subject,
                email_body=body.email_body,
                interview_type=body.interview_type,
                duration_minutes=body.duration_minutes,
                buffer_minutes=body.buffer_minutes,
                timezone=body.timezone,
                expires_at=body.expires_at,
                availability=[w.model_dump() for w in body.availability],
                recipient_email=body.recipient_email,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_link = _build_link(raw_token)
    result = outreach_service.send_session(
        db, session_id=session.id, raw_scheduling_link=raw_link,
    )
    return SendSessionResponse(
        ok=bool(result.get("ok")),
        session_id=session.id,
        status=session.status,
        error=result.get("error"),
        gmail_message_id=result.get("gmail_message_id"),
    )


# -- Batch outreach run (Phase 2.3 LangGraph agent) ---------------------------


class OutreachRunRequest(BaseModel):
    """Body for POST /jobs/{job_id}/outreach/run"""

    candidate_ids: list[UUID] = Field(
        ..., min_length=1, max_length=50,
        description="Shortlisted candidate IDs to outreach in one batch.",
    )


class OutreachRunResponse(BaseModel):
    status: str
    sent_count: int = 0
    failed_count: int = 0
    compose_errors: list[str] = []
    session_results: list[dict] = []
    analytics_event_id: str | None = None
    error: str | None = None


@router.post(
    "/jobs/{job_id}/run",
    response_model=OutreachRunResponse,
    summary="Batch outreach — compose + send + track for a list of candidates.",
    tags=["Outreach Agent"],
)
async def run_outreach_batch(
    job_id: UUID,
    body: OutreachRunRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
):
    """
    Run the full Outreach Agent pipeline (compose → send → track) for a
    list of shortlisted candidates in one call.

    Requires a connected Google integration for the calling HR user.
    """
    from app.agents.outreach.graph import build_outreach_graph

    graph = build_outreach_graph()
    state_in = {
        "job_id": str(job_id),
        "organization_id": str(ctx.organization_id),
        "hr_user_id": str(ctx.user.id),
        "candidate_ids": [str(c) for c in body.candidate_ids],
    }

    try:
        result = await graph.ainvoke(state_in)
    except Exception as exc:
        logger.exception("Outreach batch failed for job %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"outreach_failed: {exc}",
        ) from exc

    return OutreachRunResponse(
        status=result.get("status", "unknown"),
        sent_count=result.get("sent_count", 0),
        failed_count=result.get("failed_count", 0),
        compose_errors=result.get("compose_errors") or [],
        session_results=result.get("session_results") or [],
        analytics_event_id=result.get("analytics_event_id"),
        error=result.get("error"),
    )


@router.get(
    "/{candidate_id}/history",
    response_model=OutreachHistoryResponse,
)
def history(
    candidate_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    items = outreach_service.list_history(
        db,
        candidate_id=candidate_id,
        organization_id=ctx.organization_id,
    )
    return OutreachHistoryResponse(
        candidate_id=candidate_id,
        items=[OutreachHistoryItem(**i) for i in items],
    )
