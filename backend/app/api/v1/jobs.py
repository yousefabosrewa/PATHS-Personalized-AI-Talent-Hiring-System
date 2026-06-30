"""
PATHS Backend — Jobs endpoints (recruiter-facing).

GET  /jobs             — list jobs for the current org (enhanced)
GET  /jobs/{id}        — job detail
POST /jobs             — create a manual job posting
PATCH /jobs/{id}       — update job fields
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_active_user,
    get_current_hiring_org_context,
)
from app.db.models.application import Application
from app.db.models.job import Job
from app.db.models.user import User
from app.db.repositories import job_scraper_repo as scraper_repo
from app.services.hiring_pipeline import (
    STAGE_CATALOG,
    normalize_pipeline,
    pipeline_for_job,
)
from app.services.job_scraper.job_import_service import JobImportService

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Job.status values treated as publicly visible (existing DB strings only).
_PUBLIC_JOB_STATUSES = frozenset({"active", "open", "live", "published"})


# ── Schemas ────────────────────────────────────────────────────────────────

class PipelineStageIn(BaseModel):
    kind: str
    label: str | None = None
    key: str | None = None


class PipelineStageOut(BaseModel):
    key: str
    kind: str
    label: str
    group: str = "interview"


class PipelineCountOut(BaseModel):
    """Per-stage applicant count for the jobs-list mini bar chart."""

    stage: str
    label: str
    count: int


# Pipeline-ordered stages with their display labels (mirrors the frontend).
_STAGE_LABELS: list[tuple[str, str]] = [
    ("applied", "Applied"),
    ("sourced", "Sourced"),
    ("screening", "Screening"),
    ("assessment", "Assessment"),
    ("hr_interview", "HR Interview"),
    ("tech_interview", "Tech Interview"),
    ("decision", "Decision"),
    ("hired", "Hired"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
]


class JobOut(BaseModel):
    id: UUID
    title: str
    status: str
    company: str | None = None
    company_name: str | None = None
    source: str | None = None
    source_type: str | None = None
    source_platform: str | None = None
    application_mode: str = "internal_apply"
    external_apply_url: str | None = None
    visibility: str = "public"
    employment_type: str | None = None
    seniority_level: str | None = None
    workplace_type: str | None = None
    location: str | None = None
    location_text: str | None = None
    location_mode: str | None = None
    role_family: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    is_active: bool
    applicant_count: int = 0
    summary: str | None = None
    description: str | None = None
    description_text: str | None = None
    requirements: str | None = None
    job_url: str | None = None
    source_url: str | None = None
    hiring_pipeline: list[PipelineStageOut] = Field(default_factory=list)
    # Per-stage applicant counts (only stages with at least one applicant).
    pipeline_breakdown: list[PipelineCountOut] = Field(default_factory=list)
    # Structured skill requirements (job_skill_requirements rows).
    skills: list["JobSkillOut"] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDetailOut(JobOut):
    """Alias for full job payload (same shape as ``JobOut``)."""


class JobCreateRequest(BaseModel):
    title: str
    summary: str | None = None
    description_text: str | None = None
    requirements: str | None = None
    employment_type: str = "full_time"
    seniority_level: str | None = None
    workplace_type: str | None = None
    location_text: str | None = None
    role_family: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = "USD"
    min_years_experience: int | None = None
    max_years_experience: int | None = None
    hiring_pipeline: list[PipelineStageIn] | None = None
    # Required skills typed by the recruiter in Basic Info (chip input).
    skills: list[str] | None = None


class JobSkillOut(BaseModel):
    name: str
    required: bool = True


_REQUIRED_SKILLS_MARKER = "Required skills:"


def _clean_skill_list(skills: list[str] | None) -> list[str]:
    """Trim, de-duplicate (case-insensitive) and cap the recruiter's skills."""
    out: list[str] = []
    seen: set[str] = set()
    for s in skills or []:
        name = " ".join(str(s).split()).strip(" ,;")
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name[:120])
        if len(out) >= 30:
            break
    return out


def _apply_skills_to_requirements(req_text: str | None, skills: list[str]) -> str | None:
    """Mirror the structured skills into the requirements TEXT under a marker
    line, replacing any previous marker line. The match scorer and the IDSS
    job_requirement_match both scan this text, so typed skills immediately
    count toward candidate matching."""
    base = (req_text or "").strip()
    # Drop any line we previously generated.
    kept = [
        ln for ln in base.splitlines()
        if not ln.strip().lower().startswith(_REQUIRED_SKILLS_MARKER.lower())
    ]
    base = "\n".join(kept).strip()
    if not skills:
        return base or None
    line = f"{_REQUIRED_SKILLS_MARKER} {', '.join(skills)}"
    return f"{base}\n\n{line}" if base else line


def _replace_job_skill_rows(db: Session, job_id: UUID, skills: list[str]) -> None:
    """Recruiter skills become job_skill_requirements rows (is_required=True)."""
    from app.db.models.job_ingestion import JobSkillRequirement

    db.execute(
        sa_delete(JobSkillRequirement).where(
            JobSkillRequirement.job_id == job_id,
            JobSkillRequirement.extracted_by == "recruiter",
        ),
        execution_options={"synchronize_session": False},
    )
    for name in skills:
        db.add(
            JobSkillRequirement(
                job_id=job_id,
                skill_name_raw=name,
                skill_name_normalized=name.lower(),
                importance_weight=1.0,
                is_required=True,
                extracted_by="recruiter",
            )
        )


def _skills_for_jobs(db: Session, job_ids: list[UUID]) -> dict[UUID, list[JobSkillOut]]:
    from app.db.models.job_ingestion import JobSkillRequirement

    if not job_ids:
        return {}
    rows = db.execute(
        select(JobSkillRequirement).where(JobSkillRequirement.job_id.in_(job_ids))
    ).scalars().all()
    out: dict[UUID, list[JobSkillOut]] = {}
    # De-duplicate by normalized name so a skill that exists as both a scraped
    # and a recruiter-entered row only shows once on the card.
    seen: dict[UUID, set[str]] = {}
    for r in rows:
        key = (r.skill_name_normalized or r.skill_name_raw or "").strip().lower()
        bucket = seen.setdefault(r.job_id, set())
        if key in bucket:
            continue
        bucket.add(key)
        out.setdefault(r.job_id, []).append(
            JobSkillOut(name=r.skill_name_raw, required=bool(r.is_required))
        )
    return out


class JobImportRunBody(BaseModel):
    """Manual job import (compliant RSS / configured scraper source)."""

    keyword: str | None = None
    location: str | None = None
    limit: int = Field(5, ge=1, le=50)
    source: str | None = Field(
        None,
        description="Override ``JOB_SCRAPER_SOURCE`` (e.g. remoteok_rss, weworkremotely_rss, linkedin).",
    )


class JobImportRunResponse(BaseModel):
    success: bool
    found: int
    inserted: int
    duplicates: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class JobImportPipelineStatus(BaseModel):
    last_run_at: datetime | None = None
    last_success: bool | None = None
    last_inserted_count: int | None = None
    last_error: str | None = None


class JobUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    summary: str | None = None
    description_text: str | None = None
    requirements: str | None = None
    employment_type: str | None = None
    seniority_level: str | None = None
    workplace_type: str | None = None
    location_text: str | None = None
    role_family: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    is_active: bool | None = None
    application_mode: str | None = None
    visibility: str | None = None
    external_apply_url: str | None = None
    hiring_pipeline: list[PipelineStageIn] | None = None
    # When provided, replaces the recruiter-entered required skills.
    skills: list[str] | None = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _count_applicants(db: Session, job_id: UUID) -> int:
    return db.execute(
        select(func.count()).select_from(Application).where(Application.job_id == job_id)
    ).scalar_one()


def _stage_breakdown(stage_counts: dict[str, int]) -> list[PipelineCountOut]:
    """Pipeline-ordered per-stage counts, skipping empty stages. Unknown stage
    codes are appended at the end so nothing silently disappears."""
    out = [
        PipelineCountOut(stage=code, label=label, count=stage_counts[code])
        for code, label in _STAGE_LABELS
        if stage_counts.get(code)
    ]
    known = {code for code, _ in _STAGE_LABELS}
    for code, n in stage_counts.items():
        if code not in known and n:
            out.append(
                PipelineCountOut(
                    stage=code, label=code.replace("_", " ").title(), count=n,
                )
            )
    return out


def _job_out(
    job: Job,
    applicant_count: int = 0,
    pipeline_breakdown: list[PipelineCountOut] | None = None,
    skills: list[JobSkillOut] | None = None,
) -> JobOut:
    desc = job.description_text
    if desc and len(desc) > 16000:
        desc = desc[:16000] + "…"
    company = job.company_name
    src = job.source_platform or job.source_type or job.source_name
    return JobOut(
        id=job.id,
        title=job.title,
        status=job.status if hasattr(job, "status") else "published",
        company=company,
        company_name=company,
        source=src,
        source_type=job.source_type,
        source_platform=job.source_platform,
        application_mode=job.application_mode if hasattr(job, "application_mode") else "internal_apply",
        external_apply_url=job.external_apply_url if hasattr(job, "external_apply_url") else None,
        visibility=job.visibility if hasattr(job, "visibility") else "public",
        employment_type=job.employment_type,
        seniority_level=job.seniority_level,
        workplace_type=job.workplace_type,
        location=job.location_text,
        location_text=job.location_text,
        location_mode=job.location_mode if hasattr(job, "location_mode") else None,
        role_family=job.role_family,
        salary_min=float(job.salary_min) if job.salary_min else None,
        salary_max=float(job.salary_max) if job.salary_max else None,
        salary_currency=job.salary_currency,
        min_years_experience=job.min_years_experience,
        max_years_experience=job.max_years_experience,
        is_active=job.is_active,
        applicant_count=applicant_count,
        summary=job.summary,
        description=desc,
        description_text=desc,
        requirements=job.requirements,
        job_url=job.source_url,
        source_url=job.source_url,
        hiring_pipeline=[
            PipelineStageOut(
                key=s["key"], kind=s["kind"], label=s["label"],
                group=STAGE_CATALOG.get(s["kind"], {}).get("group", "interview"),
            )
            for s in pipeline_for_job(job)
        ],
        pipeline_breakdown=pipeline_breakdown or [],
        skills=skills or [],
        created_at=job.created_at if hasattr(job, "created_at") else None,
        updated_at=job.updated_at if hasattr(job, "updated_at") else None,
    )


def _job_detail_out(
    job: Job,
    applicant_count: int = 0,
    skills: list[JobSkillOut] | None = None,
) -> JobDetailOut:
    return JobDetailOut(**_job_out(job, applicant_count, skills=skills).model_dump())


def _is_publicly_listable(job: Job) -> bool:
    if not job.is_active:
        return False
    st = (job.status or "").strip().lower()
    return st in _PUBLIC_JOB_STATUSES


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post(
    "/import/run",
    response_model=JobImportRunResponse,
    summary="Run one job import cycle (RSS or configured scraper).",
)
async def run_job_import(
    body: JobImportRunBody,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
):
    _ = ctx  # hiring role required
    service = JobImportService()
    try:
        result = await service.run_import(
            limit=body.limit,
            source=body.source,
            admin_override=True,
            keyword=body.keyword,
            location=body.location,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"job_import_failed: {exc}",
        ) from exc
    ok = result.status in ("success", "partial") and result.status != "locked"
    return JobImportRunResponse(
        success=ok,
        found=result.scraped_count,
        inserted=result.inserted_count,
        duplicates=result.skipped_count,
        failed=result.failed_count,
        errors=(result.errors or [])[:25],
    )


@router.get(
    "/import/status",
    response_model=JobImportPipelineStatus,
    summary="Last job import run summary (from job_import_runs).",
)
def job_import_status(
    db: Session = Depends(get_db),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
):
    _ = ctx
    last = scraper_repo.get_latest_import_run(db)
    if last is None:
        return JobImportPipelineStatus()
    success = last.status in ("success", "partial") and not last.error_message
    return JobImportPipelineStatus(
        last_run_at=last.finished_at or last.started_at,
        last_success=success,
        last_inserted_count=last.inserted_count or 0,
        last_error=last.error_message,
    )


@router.get("", response_model=list[JobOut])
def list_jobs(
    active_only: bool = Query(False),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    keyword: str | None = Query(None, description="Search title, company, description"),
    location: str | None = None,
    source: str | None = None,
    company: str | None = None,
    status: str | None = Query(None, description="Exact job status"),
    remote: bool | None = Query(None),
    employment_type: str | None = None,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List internal jobs for the current organisation only."""
    q = select(Job).where(
        Job.organization_id == ctx.organization_id,
        Job.application_mode == "internal_apply",
    )
    if active_only:
        q = q.where(Job.is_active == True)  # noqa: E712
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.where(
            or_(
                Job.title.ilike(kw),
                Job.company_name.ilike(kw),
                Job.description_text.ilike(kw),
                Job.summary.ilike(kw),
            ),
        )
    if location and location.strip():
        loc = f"%{location.strip()}%"
        q = q.where(
            or_(
                Job.location_text.ilike(loc),
                Job.location_normalized.ilike(loc),
            ),
        )
    if source and source.strip():
        s = f"%{source.strip()}%"
        q = q.where(
            or_(
                Job.source_platform.ilike(s),
                Job.source_type.ilike(s),
                Job.source_name.ilike(s),
            ),
        )
    if company and company.strip():
        q = q.where(Job.company_name.ilike(f"%{company.strip()}%"))
    if status and status.strip():
        q = q.where(Job.status == status.strip())
    if remote is True:
        q = q.where(
            or_(
                Job.workplace_type.ilike("remote"),
                Job.location_text.ilike("%remote%"),
                Job.location_mode.ilike("%remote%"),
            ),
        )
    if employment_type and employment_type.strip():
        q = q.where(Job.employment_type.ilike(f"%{employment_type.strip()}%"))

    q = q.order_by(desc(Job.created_at)).limit(limit).offset(offset)
    jobs = db.execute(q).scalars().all()

    # One grouped query → per-job applicant totals AND per-stage breakdowns
    # (feeds the mini pipeline bar chart on each job card).
    stage_rows: list[tuple[UUID, str | None, int]] = []
    if jobs:
        stage_rows = db.execute(
            select(
                Application.job_id,
                Application.current_stage_code,
                func.count(),
            )
            .where(Application.job_id.in_([j.id for j in jobs]))
            .group_by(Application.job_id, Application.current_stage_code)
        ).all()
    counts_by_job: dict[UUID, dict[str, int]] = {}
    for job_id, stage_code, n in stage_rows:
        counts_by_job.setdefault(job_id, {})[(stage_code or "applied")] = int(n)

    skills_by_job = _skills_for_jobs(db, [j.id for j in jobs])
    results = []
    for job in jobs:
        stage_counts = counts_by_job.get(job.id, {})
        results.append(
            _job_out(
                job,
                sum(stage_counts.values()),
                pipeline_breakdown=_stage_breakdown(stage_counts),
                skills=skills_by_job.get(job.id, []),
            )
        )
    return results


@router.get("/public", response_model=list[JobOut])
def list_public_jobs(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Public job listings — no authentication required."""
    q = (
        select(Job)
        .where(
            Job.is_active == True,  # noqa: E712
            Job.status.in_(_PUBLIC_JOB_STATUSES),
        )
        .order_by(desc(Job.created_at))
        .limit(limit)
    )
    jobs = db.execute(q).scalars().all()
    results = []
    for job in jobs:
        count = _count_applicants(db, job.id)
        results.append(_job_out(job, count))
    return results


@router.get("/public/{job_id}", response_model=JobDetailOut)
def get_public_job(
    job_id: UUID,
    db: Session = Depends(get_db),
):
    """Public job detail for apply flows — only active, published-style statuses."""
    job = db.get(Job, job_id)
    if not job or not _is_publicly_listable(job):
        raise HTTPException(status_code=404, detail="Job not found")
    count = _count_applicants(db, job_id)
    return _job_detail_out(job, count)


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(
    job_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")
    count = _count_applicants(db, job_id)
    return _job_detail_out(
        job, count, skills=_skills_for_jobs(db, [job.id]).get(job.id, []),
    )


@router.post("", response_model=JobDetailOut, status_code=status.HTTP_201_CREATED)
def create_job(
    body: JobCreateRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a manual job posting for the current organisation."""
    pipeline_stages = normalize_pipeline(
        [s.model_dump() for s in body.hiring_pipeline] if body.hiring_pipeline else None
    )
    skills = _clean_skill_list(body.skills)
    job = Job(
        organization_id=ctx.organization_id,
        title=body.title,
        summary=body.summary,
        description_text=body.description_text,
        requirements=_apply_skills_to_requirements(body.requirements, skills),
        employment_type=body.employment_type or "full_time",
        seniority_level=body.seniority_level,
        workplace_type=body.workplace_type,
        location_text=body.location_text,
        role_family=body.role_family,
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        salary_currency=body.salary_currency,
        min_years_experience=body.min_years_experience,
        max_years_experience=body.max_years_experience,
        source_type="manual",
        application_mode="internal_apply",
        visibility="public",
        is_active=True,
        # Manually-created jobs from the recruiter dashboard should be live
        # straight away. The Job model defaults `status` to "draft" so we
        # must set it explicitly here (W.md §1).
        status="active",
        created_by_user_id=current_user.id,
        hiring_pipeline_jsonb=(
            {"version": 1, "stages": pipeline_stages} if pipeline_stages else None
        ),
    )
    db.add(job)
    db.flush()
    if skills:
        _replace_job_skill_rows(db, job.id, skills)
    db.commit()
    db.refresh(job)
    return _job_detail_out(
        job, 0, skills=[JobSkillOut(name=s) for s in skills],
    )


@router.patch("/{job_id}", response_model=JobDetailOut)
def update_job(
    job_id: UUID,
    body: JobUpdateRequest,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.organization_id is None:
        raise HTTPException(
            status_code=403,
            detail="Scraped platform jobs cannot be edited via org API",
        )
    if job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")

    data = body.model_dump(exclude_none=True)
    # hiring_pipeline maps to the hiring_pipeline_jsonb column (wrapped form).
    if "hiring_pipeline" in data:
        stages = normalize_pipeline(data.pop("hiring_pipeline"))
        job.hiring_pipeline_jsonb = (
            {"version": 1, "stages": stages} if stages else None
        )
    # Skills replace the recruiter-entered rows + refresh the marker line in
    # the requirements text (which match scoring scans).
    new_skills: list[str] | None = None
    if "skills" in data:
        new_skills = _clean_skill_list(data.pop("skills"))
    for field, value in data.items():
        setattr(job, field, value)
    if new_skills is not None:
        _replace_job_skill_rows(db, job.id, new_skills)
        job.requirements = _apply_skills_to_requirements(job.requirements, new_skills)

    db.commit()
    db.refresh(job)
    count = _count_applicants(db, job_id)
    return _job_detail_out(
        job, count, skills=_skills_for_jobs(db, [job.id]).get(job.id, []),
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Permanently delete an organisation's job and its dependent records.

    Several child tables reference ``jobs.id`` / ``applications.id`` WITHOUT an
    ``ON DELETE CASCADE`` (applications, candidate_job_matches,
    job_skill_requirements, job_vector_projection_status), so Postgres would
    raise a ForeignKeyViolation on a naive ``db.delete(job)``. We clear those
    explicitly first. Ordering matters: candidate_job_matches reference
    applications.id, so they must go before the applications they point at.
    Deleting the applications cascades to interviews / assessments / decision
    packets (those FKs DO declare ON DELETE CASCADE).
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.organization_id is None:
        raise HTTPException(
            status_code=403,
            detail="Scraped platform jobs cannot be deleted via org API",
        )
    if job.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.db.models.job_ingestion import (
        JobSkillRequirement,
        JobVectorProjectionStatus,
    )
    from app.db.models.sync import CandidateJobMatch

    opts = {"synchronize_session": False}
    try:
        db.execute(
            sa_delete(CandidateJobMatch).where(CandidateJobMatch.job_id == job_id),
            execution_options=opts,
        )
        db.execute(
            sa_delete(Application).where(Application.job_id == job_id),
            execution_options=opts,
        )
        db.execute(
            sa_delete(JobSkillRequirement).where(
                JobSkillRequirement.job_id == job_id
            ),
            execution_options=opts,
        )
        db.execute(
            sa_delete(JobVectorProjectionStatus).where(
                JobVectorProjectionStatus.job_id == job_id
            ),
            execution_options=opts,
        )
        # Bulk-delete the job itself (NOT db.delete(job)). Using a Core DELETE
        # avoids SQLAlchemy's ORM relationship cascade, which would otherwise
        # try to NULL applications.job_id on rows we just bulk-deleted above and
        # raise StaleDataError. The remaining children (interviews, assessments,
        # decision packets, fairness/bias/sourcing/scraper rows) all declare
        # ON DELETE CASCADE / SET NULL, so Postgres clears them for us.
        db.execute(
            sa_delete(Job).where(Job.id == job_id),
            execution_options=opts,
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive against stray FKs
        db.rollback()
        import logging

        logging.getLogger(__name__).exception(
            "Failed to delete job %s", job_id
        )
        raise HTTPException(
            status_code=409,
            detail="Job could not be deleted because it still has linked records.",
        ) from exc

    return None
