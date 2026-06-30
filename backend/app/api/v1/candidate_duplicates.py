"""
PATHS Backend — Candidate duplicate review + merge (fix2_1.md Feature 2).

Surfaced in the Candidates step/tab. Detects exact identity duplicates
(same normalized name + email + phone) and merges a group into one
canonical profile while preserving history.

Routes (mounted under /api/v1, registered BEFORE the candidates router so
the literal ``/candidates/duplicates`` paths are matched before the
catch-all ``/candidates/{candidate_id}``):

  GET  /candidates/duplicates
  POST /candidates/duplicates/{group_id}/merge
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.candidate import Candidate
from app.services.candidate_merge import (
    find_duplicate_groups,
    merge_group,
)
from app.services.candidate_merge.service import get_group_by_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["Candidate Duplicates"])


# ── Schemas ──────────────────────────────────────────────────────────────


class DuplicateCandidateOut(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DuplicateGroupOut(BaseModel):
    group_id: str
    normalized_name: str
    normalized_email: str
    normalized_phone: str
    candidate_count: int
    candidate_ids: list[str]
    candidates: list[DuplicateCandidateOut]
    last_updated: Optional[datetime] = None


class DuplicateGroupListOut(BaseModel):
    total: int
    groups: list[DuplicateGroupOut]


class MergeResultOut(BaseModel):
    merged: bool = True
    group_id: str
    canonical_candidate_id: str
    merged_candidate_ids: list[str]
    merged_count: int
    details: dict = Field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────────────────


def _source_label(cand: Candidate) -> Optional[str]:
    if cand.source_platform:
        return cand.source_platform
    return cand.source_type


def _serialize_candidate(cand: Candidate) -> DuplicateCandidateOut:
    return DuplicateCandidateOut(
        id=str(cand.id),
        name=cand.full_name or "—",
        email=cand.email,
        phone=cand.phone,
        source=_source_label(cand),
        created_at=cand.created_at,
        updated_at=cand.updated_at,
    )


# ── Routes ───────────────────────────────────────────────────────────────


@router.get("/duplicates", response_model=DuplicateGroupListOut)
def list_duplicate_groups(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> DuplicateGroupListOut:
    """Exact name+email+phone duplicate groups for the organisation."""
    groups = find_duplicate_groups(db, ctx.organization_id)
    out: list[DuplicateGroupOut] = []
    for g in groups:
        last_updated = max(
            (c.updated_at or c.created_at for c in g.candidates if (c.updated_at or c.created_at)),
            default=None,
        )
        out.append(
            DuplicateGroupOut(
                group_id=g.group_id,
                normalized_name=g.normalized_name,
                normalized_email=g.normalized_email,
                normalized_phone=g.normalized_phone,
                candidate_count=g.candidate_count,
                candidate_ids=[str(c.id) for c in g.candidates],
                candidates=[_serialize_candidate(c) for c in g.candidates],
                last_updated=last_updated,
            )
        )
    return DuplicateGroupListOut(total=len(out), groups=out)


@router.post(
    "/duplicates/{group_id}/merge",
    response_model=MergeResultOut,
    status_code=status.HTTP_200_OK,
)
def merge_duplicate_group(
    group_id: str,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> MergeResultOut:
    """Merge a duplicate group into one canonical candidate (transactional)."""
    group = get_group_by_id(db, ctx.organization_id, group_id)
    if group is None:
        raise HTTPException(
            status_code=404,
            detail="Duplicate group not found (it may have already been merged).",
        )
    try:
        outcome = merge_group(
            db,
            organization_id=ctx.organization_id,
            group_id=group_id,
            performed_by_user_id=ctx.user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MergeResultOut(
        merged=True,
        group_id=group_id,
        canonical_candidate_id=str(outcome.canonical_candidate_id),
        merged_candidate_ids=[str(c) for c in outcome.merged_candidate_ids],
        merged_count=len(outcome.merged_candidate_ids),
        details=outcome.details,
    )
