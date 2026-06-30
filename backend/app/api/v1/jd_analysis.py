"""PATHS Backend — Candidate Job-Description Analysis route (fix8&9 Update 1).

Single endpoint:

    POST /api/v1/candidates/me/job-description-analysis

Compares a pasted job description against the calling candidate's own
profile + CV evidence and returns a structured candidate-facing
analysis. The recruiter side never sees this — it's a self-service tool
for candidates.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.candidate import Candidate
from app.db.models.jd_analysis import JdAnalysis
from app.db.models.user import User
from app.services.jd_analysis import analyze_job_description_for_candidate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates/me", tags=["Candidate JD Analysis"])


def _resolve_candidate(db: Session, current_user: User) -> Candidate:
    cand = getattr(current_user, "candidate_profile", None)
    if cand is None and getattr(current_user, "email", None):
        cand = db.execute(
            select(Candidate).where(Candidate.email == current_user.email)
        ).scalars().first()
    if cand is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "This tool is only available to candidate accounts. "
                "Please sign in with your candidate account and try again."
            ),
        )
    return cand


class JdAnalysisRequest(BaseModel):
    job_description_text: str = Field(..., min_length=30, max_length=15000)


class JdAnalysisResponse(BaseModel):
    overall_fit_score: int
    summary: str
    matching_skills: list[str]
    missing_skills: list[str]
    weak_skills: list[str]
    experience_alignment: str
    project_alignment: str
    education_alignment: str
    recommended_improvements: list[str]
    interview_preparation: list[str]
    learning_recommendations: list[str]
    used_fallback: bool = False
    fallback_reason: str | None = None


@router.post(
    "/job-description-analysis",
    response_model=JdAnalysisResponse,
)
def analyze_job_description(
    body: JdAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> JdAnalysisResponse:
    """Run a JD-vs-profile analysis for the calling candidate.

    Gate on whether the user actually has a candidate profile rather than on
    the exact ``account_type`` string — that way every candidate works,
    including ones whose profile is linked by email rather than user_id.
    """
    cand = _resolve_candidate(db, current_user)

    try:
        result: dict[str, Any] = analyze_job_description_for_candidate(
            db,
            candidate_id=cand.id,
            job_description_text=body.job_description_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("[jd_analysis] failed for candidate %s", cand.id)
        raise HTTPException(status_code=500, detail="jd_analysis_failed") from exc

    # Save this analysis so the candidate keeps a history they can revisit.
    try:
        db.add(JdAnalysis(
            candidate_id=cand.id,
            job_description_text=body.job_description_text,
            result_json=result,
        ))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[jd_analysis] failed to persist analysis")

    return JdAnalysisResponse(**result)


class JdAnalysisHistoryItem(BaseModel):
    id: str
    created_at: str
    job_description_text: str
    result: dict[str, Any]


class JdAnalysisHistoryOut(BaseModel):
    items: list[JdAnalysisHistoryItem]


@router.get(
    "/job-description-analyses",
    response_model=JdAnalysisHistoryOut,
)
def list_job_description_analyses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> JdAnalysisHistoryOut:
    """Past JD analyses for the calling candidate — newest first."""
    cand = _resolve_candidate(db, current_user)
    rows = db.execute(
        select(JdAnalysis)
        .where(JdAnalysis.candidate_id == cand.id)
        .order_by(JdAnalysis.created_at.desc())
        .limit(50)
    ).scalars().all()
    return JdAnalysisHistoryOut(items=[
        JdAnalysisHistoryItem(
            id=str(r.id),
            created_at=r.created_at.isoformat() if r.created_at else "",
            job_description_text=r.job_description_text,
            result=r.result_json if isinstance(r.result_json, dict) else {},
        )
        for r in rows
    ])
