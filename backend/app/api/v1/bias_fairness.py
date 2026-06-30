"""
PATHS Backend — Bias & Fairness API (Phase 4).

Endpoints
---------
GET  /candidates/{id}/anonymized
    Return the current anonymized view for a candidate.
    Creates the view if it doesn't exist yet.

POST /candidates/{id}/deanonymize
    Request de-anonymization (reveal full profile).
    Creates a HITL approval + DeAnonEvent (pending until approved).

GET  /candidates/{id}/deanon-status
    Check whether a de-anon request has been granted.

POST /jobs/{job_id}/shortlist/propose
    Propose the current shortlist for HITL approval.
    Creates an HITLApproval of action_type="shortlist_approve".
    The shortlist is "published" only after approval.

GET  /bias/flags
    List open bias flags for the current organisation.

GET  /bias/audit
    Read bias_audit_log entries for the current organisation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.bias_fairness import (
    AnonymizedView,
    BiasAuditLog,
    BiasFlag,
    DeAnonEvent,
)
from app.db.models.hitl import HITLApproval
from app.db.models.job import Job
from app.services.bias_fairness.anonymizer import get_or_create_view, get_current_view
from app.services.bias_fairness.guardrail import log_bias_audit, raise_bias_flag

router = APIRouter(tags=["Bias & Fairness"])


# ── Pydantic schemas (inline — Phase 4 only) ─────────────────────────────────


class AnonymizedViewOut(BaseModel):
    id: str
    candidate_id: str
    view_version: int
    view_json: dict[str, Any]
    stripped_fields: list[str] | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class DeAnonRequestBody(BaseModel):
    purpose: str = "outreach"


class DeAnonEventOut(BaseModel):
    id: str
    candidate_id: str
    purpose: str
    requested_at: datetime
    granted_at: datetime | None
    denied_at: datetime | None
    approval_id: str | None

    model_config = {"from_attributes": True}


class ShortlistProposeOut(BaseModel):
    approval_id: str
    status: str
    message: str


class BiasFlagOut(BaseModel):
    id: str
    scope: str
    scope_id: str
    rule: str
    severity: str
    status: str
    detail: dict[str, Any] | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class BiasAuditOut(BaseModel):
    id: int
    event_type: str
    candidate_id: str | None
    job_id: str | None
    actor_id: str | None
    detail_json: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Anonymized view ───────────────────────────────────────────────────────────


@router.get("/candidates/{candidate_id}/anonymized", response_model=AnonymizedViewOut)
def get_anonymized_view(
    candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return (or create) the current anonymized view for a candidate.

    The view is what scoring agents receive — no PII included.
    """
    try:
        view = get_or_create_view(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    log_bias_audit(
        db,
        "anonymized_view_read",
        candidate_id=str(candidate_id),
        org_id=str(ctx.organization_id),
        actor_id=str(ctx.user.id),
    )
    db.commit()

    return AnonymizedViewOut(
        id=str(view.id),
        candidate_id=str(view.candidate_id),
        view_version=view.view_version,
        view_json=view.view_json,
        stripped_fields=view.stripped_fields,
        created_at=view.created_at,
    )


# ── De-anonymization request ──────────────────────────────────────────────────


@router.post(
    "/candidates/{candidate_id}/deanonymize",
    response_model=DeAnonEventOut,
    status_code=status.HTTP_201_CREATED,
)
def request_deanonymize(
    candidate_id: uuid.UUID,
    body: DeAnonRequestBody,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Request de-anonymization of a candidate's full profile.

    This creates:
      1. An HITLApproval of type "deanonymize" (status=pending).
      2. A DeAnonEvent linked to that approval (granted_at=None until approved).

    The frontend should redirect the user to the approvals inbox to approve.
    Once approved via POST /approvals/{id}/decide, call POST /candidates/{id}/deanonymize/grant
    to finalize the event and reveal the profile.
    """
    # Create the HITL approval gate
    approval = HITLApproval(
        id=uuid.uuid4(),
        organization_id=ctx.organization_id,
        action_type="deanonymize",
        entity_type="candidate",
        entity_id=str(candidate_id),
        entity_label=f"De-anonymize candidate {str(candidate_id)[:8]}",
        priority="medium",
        status="pending",
        requested_by_user_id=ctx.user.id,
        requested_by_name=ctx.user.full_name or ctx.user.email,
        meta_json={"purpose": body.purpose},
    )
    db.add(approval)
    db.flush()

    # Create the DeAnonEvent (pending)
    event = DeAnonEvent(
        id=uuid.uuid4(),
        org_id=ctx.organization_id,
        candidate_id=candidate_id,
        requested_by_user_id=ctx.user.id,
        approval_id=approval.id,
        purpose=body.purpose,
        granted_at=None,
    )
    db.add(event)

    # Log to bias audit
    log_bias_audit(
        db,
        "deanon_requested",
        candidate_id=str(candidate_id),
        org_id=str(ctx.organization_id),
        actor_id=str(ctx.user.id),
        detail={"purpose": body.purpose, "approval_id": str(approval.id)},
    )

    db.commit()
    db.refresh(event)

    return DeAnonEventOut(
        id=str(event.id),
        candidate_id=str(event.candidate_id),
        purpose=event.purpose,
        requested_at=event.requested_at,
        granted_at=event.granted_at,
        denied_at=event.denied_at,
        approval_id=str(event.approval_id) if event.approval_id else None,
    )


@router.get("/candidates/{candidate_id}/deanon-status", response_model=DeAnonEventOut | None)
def get_deanon_status(
    candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return the most recent de-anonymization event for this candidate in this org."""
    event = db.execute(
        select(DeAnonEvent)
        .where(
            DeAnonEvent.candidate_id == candidate_id,
            DeAnonEvent.org_id == ctx.organization_id,
        )
        .order_by(DeAnonEvent.requested_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not event:
        return None

    return DeAnonEventOut(
        id=str(event.id),
        candidate_id=str(event.candidate_id),
        purpose=event.purpose,
        requested_at=event.requested_at,
        granted_at=event.granted_at,
        denied_at=event.denied_at,
        approval_id=str(event.approval_id) if event.approval_id else None,
    )


# ── Shortlist HITL gate ────────────────────────────────────────────────────────


@router.post("/jobs/{job_id}/shortlist/propose", response_model=ShortlistProposeOut)
def propose_shortlist(
    job_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Propose the current shortlist for HITL approval.

    Creates an HITLApproval of action_type="shortlist_approve".
    The shortlist is considered "published" only after a recruiter or
    hiring manager approves via POST /approvals/{id}/decide.

    Returns 409 if a pending approval already exists for this job.
    """
    job = db.get(Job, job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")

    # Block duplicate pending proposals
    existing = db.execute(
        select(HITLApproval).where(
            HITLApproval.organization_id == ctx.organization_id,
            HITLApproval.action_type == "shortlist_approve",
            HITLApproval.entity_id == str(job_id),
            HITLApproval.status == "pending",
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pending shortlist approval already exists (id={existing.id}). "
                   "Approve or reject it before proposing a new one.",
        )

    approval = HITLApproval(
        id=uuid.uuid4(),
        organization_id=ctx.organization_id,
        action_type="shortlist_approve",
        entity_type="job",
        entity_id=str(job_id),
        entity_label=f"Shortlist for: {job.title}",
        priority="high",
        status="pending",
        requested_by_user_id=ctx.user.id,
        requested_by_name=ctx.user.full_name or ctx.user.email,
        meta_json={"job_title": job.title},
    )
    db.add(approval)

    log_bias_audit(
        db,
        "shortlist_proposed",
        job_id=str(job_id),
        org_id=str(ctx.organization_id),
        actor_id=str(ctx.user.id),
        detail={"job_title": job.title, "approval_id": str(approval.id)},
    )

    db.commit()
    db.refresh(approval)

    return ShortlistProposeOut(
        approval_id=str(approval.id),
        status="pending",
        message=(
            f"Shortlist for '{job.title}' submitted for approval. "
            f"Approval ID: {approval.id}. "
            "Use POST /approvals/{id}/decide to approve or reject."
        ),
    )


# ── Bias flags ────────────────────────────────────────────────────────────────


@router.get("/bias/flags", response_model=list[BiasFlagOut])
def list_bias_flags(
    flag_status: str | None = Query(None, alias="status"),
    scope: str | None = Query(None),
    limit: int = Query(50, le=200),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List bias flags for the current organisation."""
    q = select(BiasFlag).where(BiasFlag.org_id == ctx.organization_id)
    if flag_status:
        q = q.where(BiasFlag.status == flag_status)
    if scope:
        q = q.where(BiasFlag.scope == scope)
    q = q.order_by(BiasFlag.created_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return [
        BiasFlagOut(
            id=str(r.id),
            scope=r.scope,
            scope_id=r.scope_id,
            rule=r.rule,
            severity=r.severity,
            status=r.status,
            detail=r.detail,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ── Bias audit log ────────────────────────────────────────────────────────────


@router.get("/bias/audit", response_model=list[BiasAuditOut])
def read_bias_audit(
    event_type: str | None = Query(None),
    candidate_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Read bias_audit_log entries scoped to the current organisation."""
    q = select(BiasAuditLog).where(BiasAuditLog.org_id == str(ctx.organization_id))
    if event_type:
        q = q.where(BiasAuditLog.event_type == event_type)
    if candidate_id:
        q = q.where(BiasAuditLog.candidate_id == candidate_id)
    q = q.order_by(BiasAuditLog.created_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return [
        BiasAuditOut(
            id=r.id,
            event_type=r.event_type,
            candidate_id=r.candidate_id,
            job_id=r.job_id,
            actor_id=r.actor_id,
            detail_json=r.detail_json,
            created_at=r.created_at,
        )
        for r in rows
    ]
