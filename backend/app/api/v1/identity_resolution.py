"""
Identity Resolution Agent — detect duplicate candidates and propose safe merges.

Base URL: /api/v1/identity-resolution
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    get_current_hiring_org_context,
    OrgContext,
)
from app.db.models.identity_resolution import CandidateDuplicate, MergeHistory
from app.schemas.identity_resolution import (
    DuplicateListOut,
    DuplicateSuggestionOut,
    MergeHistoryListOut,
    MergeHistoryOut,
    MergeReviewBody,
)
import app.services.identity_resolution_service as irs

router = APIRouter(prefix="/identity-resolution", tags=["Identity Resolution"])


def _dup_to_out(d: CandidateDuplicate) -> DuplicateSuggestionOut:
    return DuplicateSuggestionOut(
        id=str(d.id),
        candidate_id_a=str(d.candidate_id_a),
        candidate_id_b=str(d.candidate_id_b),
        organization_id=str(d.organization_id),
        match_reason=d.match_reason,
        match_value=d.match_value,
        confidence=d.confidence,
        status=d.status,
        reviewed_by=str(d.reviewed_by) if d.reviewed_by else None,
        reviewed_at=d.reviewed_at,
        notes=d.notes,
        merged_into_candidate_id=str(d.merged_into_candidate_id) if d.merged_into_candidate_id else None,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


def _mh_to_out(m: MergeHistory) -> MergeHistoryOut:
    return MergeHistoryOut(
        id=str(m.id),
        organization_id=str(m.organization_id),
        kept_candidate_id=str(m.kept_candidate_id),
        removed_candidate_id=str(m.removed_candidate_id),
        merged_by=str(m.merged_by),
        merged_at=m.merged_at,
        merge_reason=m.merge_reason,
        audit_log=m.audit_log,
        created_at=m.created_at,
    )


@router.post("/scan", status_code=200)
def scan_duplicates(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Scan the organization for duplicate candidate records."""
    created = irs.suggest_duplicates(db, ctx.organization_id)
    return {
        "organization_id": str(ctx.organization_id),
        "scanned": True,
        "new_duplicates_found": len(created),
    }


@router.get("/duplicates", response_model=DuplicateListOut)
def list_duplicates(
    status: str | None = None,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List duplicate suggestions for the organization."""
    stmt = select(CandidateDuplicate).where(
        CandidateDuplicate.organization_id == ctx.organization_id,
    )
    if status:
        stmt = stmt.where(CandidateDuplicate.status == status)
    stmt = stmt.order_by(CandidateDuplicate.created_at.desc())

    items = list(db.execute(stmt).scalars().all())
    return DuplicateListOut(
        organization_id=str(ctx.organization_id),
        total=len(items),
        items=[_dup_to_out(d) for d in items],
    )


@router.post("/duplicates/{duplicate_id}/approve", response_model=DuplicateSuggestionOut)
def approve_duplicate(
    duplicate_id: str,
    body: MergeReviewBody = None,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Approve a duplicate suggestion and merge the records."""
    try:
        did = uuid.UUID(duplicate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid duplicate ID") from None

    notes = body.notes if body else None
    try:
        dup = irs.approve_merge(db, did, ctx.user.id, notes=notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _dup_to_out(dup)


@router.post("/duplicates/{duplicate_id}/reject", response_model=DuplicateSuggestionOut)
def reject_duplicate(
    duplicate_id: str,
    body: MergeReviewBody = None,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Reject a duplicate suggestion."""
    try:
        did = uuid.UUID(duplicate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid duplicate ID") from None

    notes = body.notes if body else None
    try:
        dup = irs.reject_merge(db, did, ctx.user.id, notes=notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _dup_to_out(dup)


@router.get("/merge-history", response_model=MergeHistoryListOut)
def list_merge_history(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List merge history for the organization."""
    items = irs.get_merge_history(db, ctx.organization_id)
    return MergeHistoryListOut(
        organization_id=str(ctx.organization_id),
        total=len(items),
        items=[_mh_to_out(m) for m in items],
    )
