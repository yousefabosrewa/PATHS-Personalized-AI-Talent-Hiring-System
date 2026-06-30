"""
PATHS — IDSS / Development Plan companion endpoints.

These extend the existing ``/api/v1/decision-support`` and add the
brief-mandated routes the existing router does not already cover:

  POST /api/v1/decision-support/{packet_id}/manager-decision
  GET  /api/v1/decision-support/{packet_id}/decision-report
  GET  /api/v1/decision-support/{packet_id}/report/pdf

  POST /api/v1/development-plans/generate
  GET  /api/v1/development-plans/{plan_id}
  GET  /api/v1/candidates/{candidate_id}/development-plans
  POST /api/v1/development-plans/{plan_id}/approve
  POST /api/v1/development-plans/{plan_id}/revise
  POST /api/v1/development-plans/{plan_id}/candidate-feedback
  POST /api/v1/development-plans/{plan_id}/send-feedback

Schema is unchanged — workflow status lives inside ``plan_json.status``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.decision_support import (
    DecisionEmail,
    DecisionSupportPacket,
    DevelopmentPlan,
    HrFinalDecision,
)
from app.db.models.job import Job
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.decision_support import idss_service
from app.services.decision_support.per_stage import build_per_stage_breakdown
from app.services.interview.interview_service import require_org_hr
from app.utils.decision_pdf import build_decision_report_pdf

logger = logging.getLogger(__name__)


# ── Routers ──────────────────────────────────────────────────────────────


decision_extra_router = APIRouter(
    prefix="/decision-support", tags=["Decision Support — IDSS"],
)
plans_router = APIRouter(
    prefix="/development-plans", tags=["Development Plans"],
)
candidate_plans_router = APIRouter(
    prefix="/candidates", tags=["Development Plans"],
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_packet_or_404(
    db: Session, *, packet_id: uuid.UUID, organization_id: uuid.UUID,
) -> DecisionSupportPacket:
    p = db.get(DecisionSupportPacket, packet_id)
    if p is None or p.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="packet_not_found")
    return p


def _get_plan_or_404(
    db: Session, *, plan_id: uuid.UUID, organization_id: uuid.UUID,
) -> DevelopmentPlan:
    p = db.get(DevelopmentPlan, plan_id)
    if p is None or p.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="plan_not_found")
    return p


def _resolve_org_id(user: User, body_org_id: uuid.UUID | None = None) -> uuid.UUID:
    if body_org_id is not None:
        return body_org_id
    org = next((m for m in (user.memberships or []) if m.is_active), None)
    if org is None:
        raise HTTPException(status_code=403, detail="No active organization membership.")
    return org.organization_id


# ── Schemas ──────────────────────────────────────────────────────────────


class ManagerDecisionRequest(BaseModel):
    decision: str = Field(..., description="accepted | rejected | request_more_interview | request_more_evidence")
    manager_notes: str | None = None


class GeneratePlanRequest(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    decision_id: uuid.UUID | None = None  # packet_id alias


class PlanStatusUpdateRequest(BaseModel):
    notes: str | None = None


class PlanCandidateFeedbackRequest(BaseModel):
    candidate_facing_message: str


class PlanSendFeedbackRequest(BaseModel):
    recipient_email: str | None = None  # falls back to candidate.email


# ── Manager decision (4 actions) ────────────────────────────────────────


@decision_extra_router.post("/{packet_id}/manager-decision", status_code=201)
def post_manager_decision(
    packet_id: uuid.UUID,
    body: ManagerDecisionRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    packet = _get_packet_or_404(db, packet_id=packet_id, organization_id=org_id)
    try:
        row = idss_service.record_manager_decision(
            db,
            packet=packet,
            user_id=current_user.id,
            action=body.decision,
            manager_notes=body.manager_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response: dict[str, Any] = {
        "ok": True,
        "decision": row.final_hr_decision,
        "decision_id": str(row.id),
        "packet_id": str(packet.id),
        "development_plan_id": None,
    }
    # Auto-generate dev plan for accept/reject (brief: trigger Development Agent)
    if row.final_hr_decision in {"accepted", "rejected"}:
        try:
            plan = idss_service.generate_idss_development_plan(
                db, packet=packet, actor_user_id=current_user.id,
            )
            db.flush()
            response["development_plan_id"] = str(plan.id)
        except ValueError as exc:
            response["development_plan_error"] = str(exc)
    db.commit()
    return response


# ── IDSS report (JSON) + PDF download ───────────────────────────────────


@decision_extra_router.get("/{packet_id}/decision-report")
def get_decision_report(
    packet_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    packet = _get_packet_or_404(db, packet_id=packet_id, organization_id=org_id)
    candidate = db.get(Candidate, packet.candidate_id)
    job = db.get(Job, packet.job_id)
    org = db.get(Organization, packet.organization_id)
    plan = db.execute(
        select(DevelopmentPlan)
        .where(DevelopmentPlan.decision_packet_id == packet.id)
        .order_by(DevelopmentPlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    email = db.execute(
        select(DecisionEmail)
        .where(DecisionEmail.decision_packet_id == packet.id)
        .order_by(DecisionEmail.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    hr_dec = db.execute(
        select(HrFinalDecision)
        .where(HrFinalDecision.decision_packet_id == packet.id)
        .order_by(HrFinalDecision.decided_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    per_stage = build_per_stage_breakdown(db, packet)
    return {
        "packet_id": str(packet.id),
        "per_stage_breakdown": per_stage,
        "hr_decision": {
            "final_hr_decision": hr_dec.final_hr_decision,
            "hr_notes": hr_dec.hr_notes,
            "override_reason": hr_dec.override_reason,
            "decided_at": hr_dec.decided_at.isoformat() if hr_dec.decided_at else None,
        } if hr_dec else None,
        "candidate": {
            "id": str(candidate.id) if candidate else None,
            "full_name": candidate.full_name if candidate else None,
            "current_title": candidate.current_title if candidate else None,
            "skills": list(candidate.skills or []) if candidate else [],
        },
        "job": {
            "id": str(job.id) if job else None,
            "title": job.title if job else None,
            "seniority_level": job.seniority_level if job else None,
        },
        "organization": {
            "id": str(org.id) if org else None,
            "name": org.name if org else None,
        },
        "final_score": packet.final_journey_score,
        "recommendation": packet.recommendation,
        "confidence": packet.confidence,
        "human_review_required": packet.human_review_required,
        "compliance_status": packet.compliance_status,
        "packet_json": packet.packet_json,
        "idss_v2": (packet.packet_json or {}).get("idss_v2"),
        "development_plan": {
            "id": str(plan.id),
            "plan_type": plan.plan_type,
            "status": (plan.plan_json or {}).get("status", "draft_generated"),
            "summary": plan.summary,
            "plan_json": plan.plan_json,
        } if plan else None,
        "email": {
            "id": str(email.id),
            "subject": email.subject,
            "body": email.body,
            "status": email.status,
        } if email else None,
    }


@decision_extra_router.get("/{packet_id}/report/pdf")
def get_decision_report_pdf(
    packet_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    packet = _get_packet_or_404(db, packet_id=packet_id, organization_id=org_id)
    candidate = db.get(Candidate, packet.candidate_id)
    job = db.get(Job, packet.job_id)
    org = db.get(Organization, packet.organization_id)
    plan = db.execute(
        select(DevelopmentPlan)
        .where(DevelopmentPlan.decision_packet_id == packet.id)
        .order_by(DevelopmentPlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    email = db.execute(
        select(DecisionEmail)
        .where(DecisionEmail.decision_packet_id == packet.id)
        .order_by(DecisionEmail.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    hr_dec = db.execute(
        select(HrFinalDecision)
        .where(HrFinalDecision.decision_packet_id == packet.id)
        .order_by(HrFinalDecision.decided_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    per_stage = build_per_stage_breakdown(db, packet)
    pdf_bytes = build_decision_report_pdf(
        per_stage_breakdown=per_stage,
        hr_decision={
            "final_hr_decision": hr_dec.final_hr_decision,
            "hr_notes": hr_dec.hr_notes,
            "override_reason": hr_dec.override_reason,
        } if hr_dec else None,
        candidate={
            "full_name": candidate.full_name if candidate else None,
            "current_title": candidate.current_title if candidate else None,
        },
        job={
            "title": job.title if job else None,
            "seniority_level": job.seniority_level if job else None,
        },
        organization={"name": org.name if org else None},
        packet={
            "recommendation": packet.recommendation,
            "final_journey_score": packet.final_journey_score,
            "human_review_required": packet.human_review_required,
            "idss_v2": (packet.packet_json or {}).get("idss_v2"),
            "packet_json": packet.packet_json,
        },
        development_plan=plan.plan_json if plan else None,
        decision_email={
            "subject": email.subject,
            "body": email.body,
            "status": email.status,
        } if email else None,
    )
    fname_candidate = (candidate.full_name if candidate else "Candidate") or "Candidate"
    filename = f"PATHS-Decision-Report-{fname_candidate.replace(' ', '_')}-{str(packet.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class HumanFeedbackIn(BaseModel):
    score: float = Field(ge=0, le=100)
    notes: str | None = None


@decision_extra_router.post("/{packet_id}/human-feedback")
def set_human_feedback(
    packet_id: uuid.UUID,
    body: HumanFeedbackIn,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """HR scores the human-feedback rubric stage (0-100). Stored on the packet,
    then the IDSS breakdown is recomputed so the final score reflects it."""
    from datetime import datetime, timezone

    require_org_hr(db, current_user, org_id)
    packet = _get_packet_or_404(db, packet_id=packet_id, organization_id=org_id)
    pj = dict(packet.packet_json or {})
    pj["human_feedback_input"] = {
        "score": float(body.score),
        "notes": (body.notes or "").strip() or None,
        "by": str(current_user.id),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    packet.packet_json = pj
    db.flush()
    # Recompute the rubric so the new HR score flows into the final score.
    idss_service.augment_packet_with_idss(
        db, packet=packet, application_id=packet.application_id,
    )
    db.commit()
    db.refresh(packet)
    return {
        "ok": True,
        "human_feedback_score": float(body.score),
        "final_score": packet.final_journey_score,
        "recommendation": packet.recommendation,
        "confidence": packet.confidence,
    }


# ── Development plan endpoints ──────────────────────────────────────────


@plans_router.post("/generate", status_code=201)
def post_generate_plan(
    body: GeneratePlanRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    if body.decision_id is None:
        raise HTTPException(
            status_code=400,
            detail="decision_id (packet_id) required",
        )
    packet = _get_packet_or_404(
        db, packet_id=body.decision_id, organization_id=org_id,
    )
    if packet.candidate_id != body.candidate_id or packet.job_id != body.job_id:
        raise HTTPException(status_code=400, detail="packet_candidate_or_job_mismatch")
    try:
        plan = idss_service.generate_idss_development_plan(
            db, packet=packet, actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {
        "plan_id": str(plan.id),
        "plan_type": plan.plan_type,
        "status": (plan.plan_json or {}).get("status"),
        "summary": plan.summary,
    }


@plans_router.get("/{plan_id}")
def get_plan(
    plan_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    plan = _get_plan_or_404(db, plan_id=plan_id, organization_id=org_id)
    return _serialize_plan(plan)


@candidate_plans_router.get("/{candidate_id}/development-plans")
def list_plans_for_candidate(
    candidate_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    rows = list(
        db.execute(
            select(DevelopmentPlan)
            .where(
                DevelopmentPlan.candidate_id == candidate_id,
                DevelopmentPlan.organization_id == org_id,
            )
            .order_by(DevelopmentPlan.created_at.desc())
        ).scalars().all()
    )
    return {
        "candidate_id": str(candidate_id),
        "items": [_serialize_plan(r) for r in rows],
    }


@plans_router.post("/{plan_id}/approve")
def post_approve_plan(
    plan_id: uuid.UUID,
    body: PlanStatusUpdateRequest | None = None,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    plan = _get_plan_or_404(db, plan_id=plan_id, organization_id=org_id)
    plan = idss_service.update_development_plan_status(
        db,
        plan=plan,
        status="approved",
        user_id=current_user.id,
        notes=(body.notes if body else None),
    )
    db.commit()
    return _serialize_plan(plan)


@plans_router.post("/{plan_id}/revise")
def post_revise_plan(
    plan_id: uuid.UUID,
    body: PlanStatusUpdateRequest | None = None,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    plan = _get_plan_or_404(db, plan_id=plan_id, organization_id=org_id)
    plan = idss_service.update_development_plan_status(
        db,
        plan=plan,
        status="revised",
        user_id=current_user.id,
        notes=(body.notes if body else None),
    )
    db.commit()
    return _serialize_plan(plan)


@plans_router.post("/{plan_id}/candidate-feedback")
def post_candidate_feedback_text(
    plan_id: uuid.UUID,
    body: PlanCandidateFeedbackRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    plan = _get_plan_or_404(db, plan_id=plan_id, organization_id=org_id)
    plan = idss_service.update_candidate_facing_message(
        db,
        plan=plan,
        user_id=current_user.id,
        new_message=body.candidate_facing_message,
    )
    db.commit()
    return _serialize_plan(plan)


@plans_router.post("/{plan_id}/send-feedback")
def post_send_feedback(
    plan_id: uuid.UUID,
    body: PlanSendFeedbackRequest | None = None,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, org_id)
    plan = _get_plan_or_404(db, plan_id=plan_id, organization_id=org_id)
    body_status = (plan.plan_json or {}).get("status")
    if body_status != "approved":
        raise HTTPException(
            status_code=400,
            detail="plan_must_be_approved_before_sending",
        )
    candidate = db.get(Candidate, plan.candidate_id)
    recipient = (body.recipient_email if body else None) or (
        candidate.email if candidate else None
    )
    if not recipient:
        raise HTTPException(
            status_code=400, detail="missing_recipient_email",
        )

    # Send the DEVELOPMENT PLAN's own candidate-facing message — independent of
    # the decision email (it must not require the decision email to be in any
    # particular state). Uses the same channel as outreach: the HR user's
    # Gmail, falling back to SMTP / dev-log.
    from app.db.models.job import Job
    from app.services.decision_support.decision_support_service import deliver_email

    pj = plan.plan_json or {}
    job = db.get(Job, plan.job_id)
    role = (job.title if job and job.title else None) or "this role"
    is_accepted = str(plan.plan_type or "").lower().startswith("accept") or "growth" in str(plan.plan_type or "").lower()
    subject = (
        f"Your growth & development plan — {role}"
        if is_accepted
        else f"Your development plan for {role}"
    )
    message = (
        pj.get("candidate_facing_message")
        or pj.get("candidate_facing_feedback_message")
        or pj.get("executive_summary")
        or pj.get("summary")
        or plan.summary
        or "Please find your personalized development plan below."
    )
    out = deliver_email(
        db, to=recipient, subject=subject, body=str(message),
        hr_user_id=current_user.id,
    )
    if not out.get("ok"):
        raise HTTPException(status_code=502, detail=out.get("error") or "send_failed")
    plan = idss_service.update_development_plan_status(
        db,
        plan=plan,
        status="sent",
        user_id=current_user.id,
        notes=f"sent to {recipient}",
    )
    db.commit()
    return _serialize_plan(plan)


def _serialize_plan(plan: DevelopmentPlan) -> dict[str, Any]:
    body = plan.plan_json or {}
    return {
        "id": str(plan.id),
        "decision_packet_id": str(plan.decision_packet_id),
        "candidate_id": str(plan.candidate_id),
        "job_id": str(plan.job_id),
        "plan_type": plan.plan_type,
        "status": body.get("status", "draft_generated"),
        "summary": plan.summary,
        "plan_json": body,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


__all__ = [
    "candidate_plans_router",
    "decision_extra_router",
    "plans_router",
]
