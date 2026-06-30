"""PATHS Backend — Candidate job-match routes (candidate portal dashboard).

    GET  /api/v1/candidates/me/matching-jobs
    POST /api/v1/candidates/me/matching-jobs/{job_id}/explain

Self-service endpoints for the logged-in candidate: the jobs they are most
similar to (vector match ≥ threshold) and a per-job AI explanation of why.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.jd_analysis import JdAnalysisResponse
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.candidate import Candidate
from app.db.models.interview import Interview
from app.db.models.job import Job
from app.db.models.user import User
from app.services.candidate_job_match_service import (
    explain_job_match,
    top_matching_jobs,
)
from app.services.candidate_job_seed_service import import_fresh_jobs
from app.services.interview.interview_service import mark_no_show_if_expired

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/me", tags=["Candidate Job Matches"])


class ImportFreshJobsOut(BaseModel):
    imported: int
    scraped: int
    generated: int
    source: str  # "scraped" | "generated" | "mixed"


class CandidateInterviewOut(BaseModel):
    id: str
    job_title: str | None = None
    company_name: str | None = None
    interview_type: str
    status: str
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    timezone: str | None = None
    meeting_url: str | None = None
    meeting_provider: str | None = None


class MatchingJobOut(BaseModel):
    job_id: str
    title: str
    company_name: str | None = None
    location_text: str | None = None
    workplace_type: str | None = None
    seniority_level: str | None = None
    salary_text: str | None = None
    match_score: int
    matched_skills: list[str] = []
    application_mode: str
    external_apply_url: str | None = None
    source_url: str | None = None
    source: str | None = None
    already_applied: bool = False


def _require_candidate(current_user: User, db: Session):
    """Resolve the calling user's candidate profile.

    Gates on having a candidate profile (by user link or email) rather than on
    the exact ``account_type`` string, so every candidate is accepted.
    """
    cand = getattr(current_user, "candidate_profile", None)
    if cand is None and getattr(current_user, "email", None):
        cand = db.execute(
            select(Candidate).where(Candidate.email == current_user.email)
        ).scalars().first()
    if cand is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "This is only available to candidate accounts. "
                "Please sign in with your candidate account and try again."
            ),
        )
    return cand


@router.get("/interviews", response_model=list[CandidateInterviewOut])
def get_my_interviews(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[CandidateInterviewOut]:
    """The logged-in candidate's interview invites (scheduled / rescheduled),
    upcoming first — each carries the title, time and meeting join link."""
    cand = _require_candidate(current_user, db)
    rows = db.execute(
        select(Interview, Job)
        .join(Job, Interview.job_id == Job.id, isouter=True)
        .where(
            Interview.candidate_id == cand.id,
            # Include no-shows so the candidate sees "no one joined" invites
            # (scored 0 unless rescheduled) instead of them silently vanishing.
            Interview.status.in_(["scheduled", "rescheduled", "no_show"]),
        )
        .order_by(Interview.scheduled_start_time.asc().nullslast())
    ).all()
    # Heal on read: a scheduled invite whose time passed with nobody joining
    # becomes a no_show with a zero score (all interview types).
    healed = False
    for iv, _job in rows:
        if mark_no_show_if_expired(db, iv):
            healed = True
    if healed:
        db.commit()
    return [
        CandidateInterviewOut(
            id=str(iv.id),
            job_title=job.title if job else None,
            company_name=job.company_name if job else None,
            interview_type=iv.interview_type,
            status=iv.status,
            scheduled_start_time=iv.scheduled_start_time,
            scheduled_end_time=iv.scheduled_end_time,
            timezone=iv.timezone,
            meeting_url=iv.meeting_url,
            meeting_provider=iv.meeting_provider,
        )
        for iv, job in rows
    ]


@router.post("/discover/import-fresh-jobs", response_model=ImportFreshJobsOut)
async def import_fresh_jobs_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> ImportFreshJobsOut:
    """Import 5 fresh jobs (live scrape, topped up with samples) so the
    candidate immediately sees new openings on the Open Jobs page."""
    _require_candidate(current_user, db)
    try:
        summary = await import_fresh_jobs(db, limit=5)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[discover_import] import failed")
        raise HTTPException(status_code=500, detail="import_failed") from exc
    return ImportFreshJobsOut(**summary)


@router.get("/matching-jobs", response_model=list[MatchingJobOut])
def get_matching_jobs(
    min_score: float = Query(50.0, ge=0, le=100),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[MatchingJobOut]:
    """The candidate's top matching active jobs (similarity ≥ ``min_score``)."""
    cand = _require_candidate(current_user, db)
    rows = top_matching_jobs(
        db, candidate_id=cand.id, min_score=min_score, limit=limit,
    )
    return [MatchingJobOut(**r) for r in rows]


@router.post("/matching-jobs/{job_id}/explain", response_model=JdAnalysisResponse)
def explain_matching_job(
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> JdAnalysisResponse:
    """Explain why a specific job matches the calling candidate."""
    cand = _require_candidate(current_user, db)
    try:
        result = explain_job_match(db, candidate_id=cand.id, job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[candidate_match] explain failed for job %s", job_id)
        raise HTTPException(status_code=500, detail="explain_failed") from exc
    return JdAnalysisResponse(**result)
