"""
PATHS Backend — HITL Approval endpoints.

GET  /approvals          — list approvals for the current org (filterable by status)
POST /approvals          — create a new approval request
POST /approvals/{id}/decide — approve or reject a pending approval
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.bias_fairness import DeAnonEvent
from app.db.models.hitl import HITLApproval
from app.schemas.hitl import HITLApprovalOut, HITLCreateRequest, HITLDecideRequest

router = APIRouter(prefix="/approvals", tags=["HITL Approvals"])


@router.get("", response_model=list[HITLApprovalOut])
def list_approvals(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List HITL approvals for the current organisation."""
    q = select(HITLApproval).where(HITLApproval.organization_id == ctx.organization_id)
    if status_filter:
        q = q.where(HITLApproval.status == status_filter)
    q = q.order_by(HITLApproval.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(q).scalars().all()
    return [HITLApprovalOut.model_validate(r) for r in rows]


@router.post("", response_model=HITLApprovalOut, status_code=status.HTTP_201_CREATED)
def create_approval(
    body: HITLCreateRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Create a new HITL approval request."""
    approval = HITLApproval(
        organization_id=ctx.organization_id,
        action_type=body.action_type,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_label=body.entity_label,
        priority=body.priority,
        requested_by_user_id=ctx.user.id,
        requested_by_name=ctx.user.full_name or ctx.user.email,
        expires_at=body.expires_at,
        meta_json=body.meta_json,
        status="pending",
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return HITLApprovalOut.model_validate(approval)


@router.post("/{approval_id}/decide", response_model=HITLApprovalOut)
def decide_approval(
    approval_id: UUID,
    body: HITLDecideRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Approve or reject a pending HITL approval."""
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    approval = db.get(HITLApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.organization_id != ctx.organization_id:
        raise HTTPException(status_code=403, detail="Approval belongs to a different organisation")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval is already '{approval.status}'")

    approval.status = body.decision
    approval.decision = body.decision
    approval.reason = body.reason
    approval.reviewed_by_user_id = ctx.user.id
    approval.reviewed_by_name = ctx.user.full_name or ctx.user.email
    approval.reviewed_at = datetime.now(timezone.utc)

    # Candidate.md §2 — when an HR Manager decides a de-anonymization
    # approval, propagate the decision to the linked DeAnonEvent so the
    # candidate's identity is actually revealed (approved) or kept masked
    # (rejected). Without this, approving in the inbox never unmasked.
    if approval.action_type == "deanonymize":
        event = db.execute(
            select(DeAnonEvent).where(DeAnonEvent.approval_id == approval.id)
        ).scalar_one_or_none()
        if event is not None:
            now = datetime.now(timezone.utc)
            if body.decision == "approved":
                event.granted_at = now
                event.denied_at = None
            else:  # rejected
                event.denied_at = now
                event.granted_at = None

    db.commit()
    db.refresh(approval)
    return HITLApprovalOut.model_validate(approval)
