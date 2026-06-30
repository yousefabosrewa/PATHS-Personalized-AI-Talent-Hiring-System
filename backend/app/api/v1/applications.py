"""
PATHS Backend — Application endpoints.

GET  /applications                    — list applications for the org
GET  /applications/{id}               — application detail
GET  /jobs/{job_id}/applications      — applications for a specific job
PATCH /applications/{id}/stage        — advance/move pipeline stage
GET  /jobs/{job_id}/shortlist         — scored + ranked shortlist for a job
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, tuple_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import Application
from app.db.models.job import Job
from app.db.models.scoring import CandidateJobScore
from app.schemas.application import ApplicationOut, ShortlistItemOut, StageTransitionRequest
from app.services.candidate_job_match_service import candidate_job_match_score
from app.services.hiring_pipeline import build_candidate_roadmap, pipeline_for_job

router = APIRouter(tags=["Applications"])

VALID_STAGES = {
    "applied", "sourced", "screening", "assessment",
    "hr_interview", "tech_interview", "decision", "hired", "rejected", "withdrawn",
}


def _app_out(
    app: Application,
    score: CandidateJobScore | None = None,
    fallback_match: float | None = None,
) -> ApplicationOut:
    cand = app.candidate
    title = None
    skills: list[str] = []
    if cand:
        title = (cand.current_title or cand.headline or "").strip() or None
        skills = list(cand.skills or [])
    match_final = None
    match_conf = None
    if score is not None:
        match_final = float(score.final_score) if score.final_score is not None else None
        match_conf = float(score.confidence) if score.confidence is not None else None
    # No row in candidate_job_scores (the optional scoring agent's table) —
    # fall back to the live skills/title blend so this list agrees with the
    # per-job Candidates tab and the candidate's own dashboard.
    if match_final is None:
        match_final = fallback_match
    # The candidate has a match score (so their CV has been screened) when they
    # have skills/title to match on, or an explicit screening score exists.
    has_match = bool(cand and ((cand.skills or []) or cand.current_title)) or (
        match_final is not None
    )
    return ApplicationOut(
        id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        application_type=app.application_type,
        source_channel=app.source_channel,
        current_stage_code=app.current_stage_code,
        overall_status=app.overall_status,
        created_at=app.created_at,
        updated_at=getattr(app, "updated_at", None),
        candidate_name=cand.full_name if cand else None,
        candidate_email=cand.email if cand else None,
        candidate_current_title=title,
        candidate_skills=skills,
        job_title=app.job.title if app.job else None,
        match_final_score=match_final,
        match_confidence=match_conf,
        roadmap=build_candidate_roadmap(
            pipeline_for_job(app.job) if app.job else [],
            app.current_stage_code,
            app.overall_status,
            has_match_score=has_match,
        ),
    )


@router.get("/applications", response_model=list[ApplicationOut])
def list_applications(
    stage: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List all applications for the current organisation's jobs."""
    q = (
        select(Application)
        .join(Job, Application.job_id == Job.id)
        .where(Job.organization_id == ctx.organization_id)
    )
    if stage:
        q = q.where(Application.current_stage_code == stage)
    q = q.order_by(desc(Application.created_at)).limit(limit).offset(offset)
    rows = db.execute(q).scalars().all()
    pairs = list({(r.candidate_id, r.job_id) for r in rows})
    score_map: dict[tuple[object, object], CandidateJobScore] = {}
    if pairs:
        score_rows = db.execute(
            select(CandidateJobScore).where(
                tuple_(CandidateJobScore.candidate_id, CandidateJobScore.job_id).in_(
                    pairs
                )
            )
        ).scalars().all()
        score_map = {(s.candidate_id, s.job_id): s for s in score_rows}
    out: list[ApplicationOut] = []
    blend_cache: dict[tuple[object, object], float | None] = {}
    for r in rows:
        s = score_map.get((r.candidate_id, r.job_id))
        fallback: float | None = None
        if (s is None or s.final_score is None) and r.job is not None:
            key = (r.candidate_id, r.job_id)
            if key not in blend_cache:
                m = candidate_job_match_score(db, candidate_id=r.candidate_id, job=r.job)
                blend_cache[key] = float(m[0]) if m else None
            fallback = blend_cache[key]
        out.append(_app_out(r, s, fallback_match=fallback))
    return out


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = db.get(Job, app.job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=403, detail="Application not in your organisation")
    score = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.candidate_id == app.candidate_id,
            CandidateJobScore.job_id == app.job_id,
        ).limit(1)
    ).scalar_one_or_none()
    fallback: float | None = None
    if score is None or score.final_score is None:
        m = candidate_job_match_score(db, candidate_id=app.candidate_id, job=job)
        fallback = float(m[0]) if m else None
    return _app_out(app, score, fallback_match=fallback)


@router.get("/jobs/{job_id}/applications", response_model=list[ApplicationOut])
def list_job_applications(
    job_id: UUID,
    stage: str | None = Query(None),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")
    q = select(Application).where(Application.job_id == job_id)
    if stage:
        q = q.where(Application.current_stage_code == stage)
    q = q.order_by(desc(Application.created_at))
    rows = db.execute(q).scalars().all()
    pairs = list({(r.candidate_id, r.job_id) for r in rows})
    score_map: dict[tuple[object, object], CandidateJobScore] = {}
    if pairs:
        score_rows = db.execute(
            select(CandidateJobScore).where(
                tuple_(CandidateJobScore.candidate_id, CandidateJobScore.job_id).in_(
                    pairs
                )
            )
        ).scalars().all()
        score_map = {(s.candidate_id, s.job_id): s for s in score_rows}
    out: list[ApplicationOut] = []
    blend_cache: dict[tuple[object, object], float | None] = {}
    for r in rows:
        s = score_map.get((r.candidate_id, r.job_id))
        fallback: float | None = None
        if (s is None or s.final_score is None) and r.job is not None:
            key = (r.candidate_id, r.job_id)
            if key not in blend_cache:
                m = candidate_job_match_score(db, candidate_id=r.candidate_id, job=r.job)
                blend_cache[key] = float(m[0]) if m else None
            fallback = blend_cache[key]
        out.append(_app_out(r, s, fallback_match=fallback))
    return out


@router.patch("/applications/{application_id}/stage", response_model=ApplicationOut)
def advance_stage(
    application_id: UUID,
    body: StageTransitionRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Move an application to a new pipeline stage."""
    if body.stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage '{body.stage}'")

    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = db.get(Job, app.job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=403, detail="Application not in your organisation")

    app.current_stage_code = body.stage
    if body.stage in ("hired", "rejected", "withdrawn"):
        app.overall_status = body.stage
    db.commit()
    db.refresh(app)
    score = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.candidate_id == app.candidate_id,
            CandidateJobScore.job_id == app.job_id,
        ).limit(1)
    ).scalar_one_or_none()
    fallback: float | None = None
    if score is None or score.final_score is None:
        m = candidate_job_match_score(db, candidate_id=app.candidate_id, job=job)
        fallback = float(m[0]) if m else None
    return _app_out(app, score, fallback_match=fallback)


@router.get("/jobs/{job_id}/shortlist", response_model=list[ShortlistItemOut])
def get_shortlist(
    job_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return scored + ranked shortlist for a job."""
    job = db.get(Job, job_id)
    if not job or job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get all applications for this job
    apps = db.execute(
        select(Application).where(Application.job_id == job_id)
        .order_by(desc(Application.created_at))
    ).scalars().all()

    if not apps:
        return []

    candidate_ids = [a.candidate_id for a in apps]

    # Get scores for all candidates against this job
    scores = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.job_id == job_id,
            CandidateJobScore.candidate_id.in_(candidate_ids),
        )
    ).scalars().all()
    score_map = {s.candidate_id: s for s in scores}

    results: list[ShortlistItemOut] = []
    for app in apps:
        cand = app.candidate
        score = score_map.get(app.candidate_id)
        results.append(ShortlistItemOut(
            application_id=app.id,
            candidate_id=app.candidate_id,
            candidate_name=cand.full_name if cand else None,
            current_stage_code=app.current_stage_code,
            final_score=float(score.final_score) if score else None,
            agent_score=float(score.agent_score) if score else None,
            vector_similarity_score=float(score.vector_similarity_score) if score else None,
            confidence=float(score.confidence) if score and score.confidence else None,
            explanation=score.explanation if score else None,
            strengths=list(score.strengths or []) if score else [],
            weaknesses=list(score.weaknesses or []) if score else [],
            matched_skills=list(score.matched_skills or []) if score else [],
            missing_required_skills=list(score.missing_required_skills or []) if score else [],
            criteria_breakdown=score.criteria_breakdown if score else None,
        ))

    # Sort by final_score descending (un-scored go last)
    results.sort(key=lambda x: (x.final_score is None, -(x.final_score or 0)))
    for i, r in enumerate(results):
        r.rank = i + 1

    return results
