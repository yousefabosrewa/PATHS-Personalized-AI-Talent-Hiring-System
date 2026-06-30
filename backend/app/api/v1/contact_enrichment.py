from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.schemas.contact_enrichment import (
    ContactApprovalBody,
    EnrichedContactOut,
    EnrichmentStatusOut,
)
from app.services import contact_enrichment_service as service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact-enrichment", tags=["Contact Enrichment"])


@router.get("/status", response_model=EnrichmentStatusOut)
def get_enrichment_status(
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Return summary stats for enriched contacts (pending/approved/rejected by type)."""
    return service.get_enrichment_status(db, ctx.organization_id)


@router.get("/contacts", response_model=list[EnrichedContactOut])
def list_enriched_contacts(
    status: str | None = Query(None, description="Filter by status: pending, approved, rejected"),
    contact_type: str | None = Query(None, description="Filter by type: email, phone, linkedin, github, portfolio"),
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """List enriched contacts with optional status/type filters."""
    return service.list_contacts(db, ctx.organization_id, status=status, contact_type=contact_type)


@router.get("/interview-candidates")
def list_interview_candidates(
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Candidates in the interview process, with their contact info + which
    channels are missing (Contact Finder)."""
    return service.list_interview_candidates(db, ctx.organization_id)


@router.post("/candidates/{candidate_id}/enrich")
def enrich_candidate(
    candidate_id: UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Search available sources (GitHub profile, configured LinkedIn MCP) using
    the candidate's existing data to fill in missing contact channels."""
    return service.enrich_candidate(db, ctx.organization_id, candidate_id)


@router.post("/contacts/{contact_id}/approve", response_model=EnrichedContactOut)
def approve_contact(
    contact_id: UUID,
    body: ContactApprovalBody = ContactApprovalBody(),
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Approve a pending enriched contact."""
    return service.approve_contact(db, contact_id, ctx.organization_id, reviewer=body.reviewer_name)


@router.post("/contacts/{contact_id}/reject", response_model=EnrichedContactOut)
def reject_contact(
    contact_id: UUID,
    body: ContactApprovalBody = ContactApprovalBody(),
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Reject a pending enriched contact."""
    return service.reject_contact(db, contact_id, ctx.organization_id, reviewer=body.reviewer_name)
