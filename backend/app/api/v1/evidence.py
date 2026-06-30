"""
PATHS Backend — Evidence & Sources API (Phase 2 completion).

Blueprint Law #1: Every agent claim must reference a persisted evidence_item.

Endpoints
---------
GET  /candidates/{id}/evidence          list evidence items for a candidate
GET  /candidates/{id}/evidence/{eid}    get a single evidence item
GET  /candidates/{id}/sources           list source documents for a candidate
POST /candidates/{id}/sources           add a manual source (recruiter entry)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.candidate_access import org_can_view_candidate
from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.candidate import Candidate
from app.db.models.evidence import CandidateSource, EvidenceItem

router = APIRouter(tags=["Evidence"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class EvidenceItemOut(BaseModel):
    id: str
    candidate_id: str
    ingestion_job_id: str | None
    type: str
    field_ref: str | None
    source_uri: str | None
    extracted_text: str | None
    confidence: float | None
    meta_json: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CandidateSourceOut(BaseModel):
    id: str
    candidate_id: str
    source: str
    url: str | None
    raw_blob_uri: str | None
    fetched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AddSourceBody(BaseModel):
    source: str
    url: str | None = None
    raw_blob_uri: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _require_candidate(db: Session, candidate_id: uuid.UUID) -> Candidate:
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    return cand


# ── Evidence items ────────────────────────────────────────────────────────────


@router.get(
    "/candidates/{candidate_id}/evidence",
    response_model=list[EvidenceItemOut],
)
def list_evidence(
    candidate_id: uuid.UUID,
    type_filter: str | None = Query(None, alias="type"),
    field_ref: str | None = Query(None),
    limit: int = Query(100, le=500),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List all evidence items for a candidate.

    Query params:
      type      — filter by evidence type (cv_claim, github_repo, …)
      field_ref — filter by field reference (e.g. "skill:python")
      limit     — max rows (default 100, max 500)
    """
    _require_candidate(db, candidate_id)
    if not org_can_view_candidate(db, ctx.organization_id, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    q = select(EvidenceItem).where(EvidenceItem.candidate_id == candidate_id)
    if type_filter:
        q = q.where(EvidenceItem.type == type_filter)
    if field_ref:
        q = q.where(EvidenceItem.field_ref == field_ref)
    q = q.order_by(EvidenceItem.created_at.desc()).limit(limit)

    rows = db.execute(q).scalars().all()
    return [
        EvidenceItemOut(
            id=str(r.id),
            candidate_id=str(r.candidate_id),
            ingestion_job_id=r.ingestion_job_id,
            type=r.type,
            field_ref=r.field_ref,
            source_uri=r.source_uri,
            extracted_text=r.extracted_text,
            confidence=r.confidence,
            meta_json=r.meta_json,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/candidates/{candidate_id}/evidence/{evidence_id}",
    response_model=EvidenceItemOut,
)
def get_evidence_item(
    candidate_id: uuid.UUID,
    evidence_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return a single evidence item."""
    _require_candidate(db, candidate_id)
    if not org_can_view_candidate(db, ctx.organization_id, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    item = db.execute(
        select(EvidenceItem).where(
            EvidenceItem.id == evidence_id,
            EvidenceItem.candidate_id == candidate_id,
        )
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    return EvidenceItemOut(
        id=str(item.id),
        candidate_id=str(item.candidate_id),
        ingestion_job_id=item.ingestion_job_id,
        type=item.type,
        field_ref=item.field_ref,
        source_uri=item.source_uri,
        extracted_text=item.extracted_text,
        confidence=item.confidence,
        meta_json=item.meta_json,
        created_at=item.created_at,
    )


# ── Candidate sources ─────────────────────────────────────────────────────────


@router.get(
    "/candidates/{candidate_id}/sources",
    response_model=list[CandidateSourceOut],
)
def list_sources(
    candidate_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List all source documents/profiles for a candidate."""
    _require_candidate(db, candidate_id)
    if not org_can_view_candidate(db, ctx.organization_id, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    rows = db.execute(
        select(CandidateSource)
        .where(CandidateSource.candidate_id == candidate_id)
        .order_by(CandidateSource.created_at.desc())
    ).scalars().all()

    return [
        CandidateSourceOut(
            id=str(r.id),
            candidate_id=str(r.candidate_id),
            source=r.source,
            url=r.url,
            raw_blob_uri=r.raw_blob_uri,
            fetched_at=r.fetched_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "/candidates/{candidate_id}/sources",
    response_model=CandidateSourceOut,
    status_code=status.HTTP_201_CREATED,
)
def add_source(
    candidate_id: uuid.UUID,
    body: AddSourceBody,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Manually attach an external source to a candidate (e.g. LinkedIn URL)."""
    _require_candidate(db, candidate_id)
    if not org_can_view_candidate(db, ctx.organization_id, candidate_id):
        raise HTTPException(status_code=404, detail="Candidate not found")

    src = CandidateSource(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        source=body.source,
        url=body.url,
        raw_blob_uri=body.raw_blob_uri,
        fetched_at=None,
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    return CandidateSourceOut(
        id=str(src.id),
        candidate_id=str(src.candidate_id),
        source=src.source,
        url=src.url,
        raw_blob_uri=src.raw_blob_uri,
        fetched_at=src.fetched_at,
        created_at=src.created_at,
    )
