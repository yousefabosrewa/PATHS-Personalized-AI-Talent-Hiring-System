"""
PATHS Backend — Unauthenticated public endpoints.

GET /api/v1/public/platform-stats  — hero counters
GET /api/v1/public/plans           — pricing plans
GET /api/v1/public/jobs            — public job board listing
GET /api/v1/public/jobs/{slug}     — single job detail

PATHS-124 (Phase 6 — Commercial Launch)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models.application import Application
from app.db.models.billing import Plan
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.organization import Organization

router = APIRouter(prefix="/public", tags=["Public"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class PlatformStats(BaseModel):
    orgs_count: int
    cvs_processed: int
    active_jobs: int
    placements: int


class PublicPlanOut(BaseModel):
    id: str
    name: str
    code: str
    price_monthly_cents: int
    price_annual_cents: int
    currency: str
    limits: dict
    features: list


class PublicJobOut(BaseModel):
    id: str
    slug: str
    title: str
    company: str
    location: str
    work_mode: str | None
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    level: str | None
    description_preview: str | None
    # schema.org fields
    date_posted: str | None
    valid_through: str | None


class PublicJobDetail(PublicJobOut):
    description_full: str | None
    required_skills: list[str]
    preferred_skills: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _job_to_slug(job: Job) -> str:
    title_slug = job.title.lower().replace(" ", "-").replace("/", "-")[:60]
    return f"{title_slug}-{str(job.id)[:8]}"


def _job_to_public(job: Job) -> PublicJobOut:
    company_name = ""
    try:
        if hasattr(job, "organization") and job.organization:
            company_name = job.organization.name
    except Exception:
        pass

    desc = getattr(job, "description", None) or getattr(job, "raw_description", None) or ""
    return PublicJobOut(
        id=str(job.id),
        slug=_job_to_slug(job),
        title=job.title or "",
        company=company_name,
        location=getattr(job, "location", "") or "",
        work_mode=getattr(job, "work_mode", None),
        employment_type=getattr(job, "employment_type", None),
        salary_min=getattr(job, "salary_min", None),
        salary_max=getattr(job, "salary_max", None),
        currency=getattr(job, "salary_currency", None),
        level=getattr(job, "level", None),
        description_preview=desc[:280] if desc else None,
        date_posted=job.created_at.isoformat() if getattr(job, "created_at", None) else None,
        valid_through=job.closed_at.isoformat() if getattr(job, "closed_at", None) else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/platform-stats", response_model=PlatformStats)
def platform_stats(db: Session = Depends(get_db)):
    """Hero counters shown on the public landing page."""
    orgs = db.query(func.count(Organization.id)).scalar() or 0
    cvs = db.query(func.count(Candidate.id)).scalar() or 0
    active_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.status == "published")
        .scalar()
        or 0
    )
    placements = (
        db.query(func.count(Application.id))
        .filter(Application.current_stage_code == "hired")
        .scalar()
        or 0
    )
    return PlatformStats(
        orgs_count=orgs,
        cvs_processed=cvs,
        active_jobs=active_jobs,
        placements=placements,
    )


@router.get("/plans", response_model=list[PublicPlanOut])
def public_plans(db: Session = Depends(get_db)):
    """Public plan list for the /pricing page."""
    plans = db.query(Plan).filter(Plan.is_public.is_(True)).all()
    return [
        PublicPlanOut(
            id=str(p.id),
            name=p.name,
            code=p.code,
            price_monthly_cents=p.price_monthly_cents,
            price_annual_cents=p.price_annual_cents,
            currency=p.currency,
            limits=p.limits or {},
            features=p.features or [],
        )
        for p in plans
    ]


@router.get("/jobs", response_model=list[PublicJobOut])
def public_jobs(
    q: str = Query(default="", description="Full-text search"),
    location: str = Query(default=""),
    work_mode: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public job board listing — returns published jobs from all orgs."""
    query = db.query(Job).filter(Job.status == "published")

    if q:
        query = query.filter(Job.title.ilike(f"%{q}%"))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if work_mode:
        query = query.filter(Job.work_mode == work_mode)

    offset = (page - 1) * page_size
    jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size).all()
    return [_job_to_public(j) for j in jobs]


@router.get("/jobs/{slug}", response_model=PublicJobDetail)
def public_job_detail(slug: str, db: Session = Depends(get_db)):
    """
    Single public job detail.

    The slug format is ``{title-slug}-{first-8-chars-of-id}``, so we extract
    the id suffix to look up the canonical job.
    """
    # slug ends with -{8-char-prefix}
    parts = slug.rsplit("-", 1)
    id_prefix = parts[-1] if len(parts) > 1 else slug

    # Find jobs whose UUID starts with the prefix
    all_published = db.query(Job).filter(Job.status == "published").all()
    job = next(
        (j for j in all_published if str(j.id).replace("-", "").startswith(id_prefix)),
        None,
    )
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    base = _job_to_public(job)
    desc = getattr(job, "description", None) or getattr(job, "raw_description", None) or ""

    # Pull skills if available
    req_skills: list[str] = []
    pref_skills: list[str] = []
    try:
        if hasattr(job, "skills"):
            for js in job.skills:
                skill_name = getattr(js, "name", None) or getattr(
                    getattr(js, "skill", None), "name", ""
                )
                if getattr(js, "required", True):
                    req_skills.append(skill_name)
                else:
                    pref_skills.append(skill_name)
    except Exception:
        pass

    return PublicJobDetail(
        **base.model_dump(),
        description_full=desc or None,
        description_preview=desc[:280] if desc else None,
        required_skills=req_skills,
        preferred_skills=pref_skills,
    )
