"""
PATHS Backend — Candidate Application endpoints (Phase 1).

PUT /candidate-applications/{app_id}/stage       — move pipeline stage
PUT /jobs/{job_id}/fairness-rubric               — upsert fairness rubric
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import Application
from app.db.models.fairness_rubric import FairnessRubric
from app.db.models.job import Job

router = APIRouter(tags=["Pipeline"])

VALID_STAGES = frozenset([
    "define", "source", "screen", "shortlist",
    "reveal", "outreach", "interview", "evaluate", "decide",
])


# ── Schemas ───────────────────────────────────────────────────────────────

class MoveStageRequest(BaseModel):
    stage: str = Field(..., description="One of the 9 pipeline stage keys")


class MoveStageOut(BaseModel):
    id: UUID
    stage: str
    updated_at: str


class FairnessRubricIn(BaseModel):
    protected_attrs: dict = Field(default_factory=dict)
    disparate_impact_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    enabled: bool = True


class FairnessRubricOut(BaseModel):
    id: UUID
    job_id: UUID
    protected_attrs: dict
    disparate_impact_threshold: float
    enabled: bool
    created_at: str
    updated_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.put("/candidate-applications/{app_id}/stage", response_model=MoveStageOut)
def move_application_stage(
    app_id: UUID,
    body: MoveStageRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> MoveStageOut:
    if body.stage not in VALID_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stage '{body.stage}'. Valid: {sorted(VALID_STAGES)}",
        )

    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    # Tenant isolation: the application's job must belong to the current org.
    job = db.get(Job, app.job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application does not belong to your organization.",
        )

    app.pipeline_stage = body.stage
    db.commit()
    db.refresh(app)

    updated = app.updated_at if app.updated_at else datetime.utcnow()
    return MoveStageOut(id=app.id, stage=app.pipeline_stage, updated_at=updated.isoformat())


@router.put("/jobs/{job_id}/fairness-rubric", response_model=FairnessRubricOut)
def upsert_fairness_rubric(
    job_id: UUID,
    body: FairnessRubricIn,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> FairnessRubricOut:
    job = db.get(Job, job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    rubric = db.query(FairnessRubric).filter(FairnessRubric.job_id == job_id).first()
    if rubric is None:
        rubric = FairnessRubric(
            id=uuid4(),
            job_id=job_id,
            protected_attrs=body.protected_attrs,
            disparate_impact_threshold=body.disparate_impact_threshold,
            enabled=body.enabled,
        )
        db.add(rubric)
    else:
        rubric.protected_attrs = body.protected_attrs
        rubric.disparate_impact_threshold = body.disparate_impact_threshold
        rubric.enabled = body.enabled

    db.commit()
    db.refresh(rubric)

    return FairnessRubricOut(
        id=rubric.id,
        job_id=rubric.job_id,
        protected_attrs=rubric.protected_attrs,
        disparate_impact_threshold=rubric.disparate_impact_threshold,
        enabled=rubric.enabled,
        created_at=rubric.created_at.isoformat(),
        updated_at=rubric.updated_at.isoformat(),
    )
