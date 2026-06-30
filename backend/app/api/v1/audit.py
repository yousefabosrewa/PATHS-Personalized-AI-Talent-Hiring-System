"""
PATHS Backend — Audit log endpoints.

GET /audit — paginated audit events for the current org
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import AuditEvent
from pydantic import BaseModel
from datetime import datetime


class AuditEventOut(BaseModel):
    id: int
    actor_type: str
    actor_id: str
    entity_type: str
    entity_id: str
    action: str
    before_jsonb: dict | None = None
    after_jsonb: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    search: str | None = Query(None, description="Filter by action or entity_type"),
    entity_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """
    Return audit events scoped to the current organisation.
    actor_id is matched against org member user IDs, or entity_id contains org_id.
    """
    # Fetch org member user IDs for scoping
    from app.db.models.application import OrganizationMember
    member_ids = db.execute(
        select(OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == ctx.organization_id,
            OrganizationMember.is_active == True,  # noqa: E712
        )
    ).scalars().all()
    member_id_strs = [str(mid) for mid in member_ids]

    q = select(AuditEvent).where(
        or_(
            AuditEvent.actor_id.in_(member_id_strs),
            AuditEvent.entity_id.contains(str(ctx.organization_id)),
            # Platform job-scraper / import audit rows (actor_type=system)
            and_(
                AuditEvent.actor_type == "system",
                AuditEvent.entity_type.in_(
                    ("job_import_run", "job", "job_scraper"),
                ),
            ),
        )
    )

    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)

    if search:
        q = q.where(
            or_(
                AuditEvent.action.ilike(f"%{search}%"),
                AuditEvent.entity_type.ilike(f"%{search}%"),
            )
        )

    q = q.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    rows = db.execute(q).scalars().all()
    return [AuditEventOut.model_validate(r) for r in rows]
