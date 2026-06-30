"""
PATHS Backend — Assessment Agent API endpoints (fix5.md refactor).

The canonical flow is now **job-level templates**:

  POST   /assessments/generate-draft       — generate a draft via the LLM
  GET    /assessments/{id}                 — get one draft / published assessment
  PATCH  /assessments/{id}                 — edit draft questions / metadata
  POST   /assessments/{id}/approve         — flip status from draft → published
  GET    /jobs/{job_id}/assessments        — list job-level assessments
  POST   /assessments/upload-source-file   — upload reference material
  GET    /jobs/{job_id}/published-assessments
                                           — candidate-facing: only published

Legacy per-candidate endpoints are kept for backwards compatibility with
the old listing UI:

  POST   /assessments                      — direct create (legacy fields stay optional)
  GET    /assessments?application_id=...   — list (existing call sites)
  DELETE /assessments/{id}                 — delete a draft / template
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.application import Application
from app.db.models.assessment import Assessment
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.services.assessment_agent import (
    ASSESSMENT_TYPES,
    AssessmentType,
    generate_assessment_draft,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assessments", tags=["Assessment Agent"])
job_router = APIRouter(prefix="/jobs", tags=["Assessment Agent"])


# ── Status constants ────────────────────────────────────────────────────────


_DRAFT = "draft"
_PUBLISHED = "published"     # canonical "approved + active"
_APPROVED = "approved"       # alias accepted on input
_ARCHIVED = "archived"

# Statuses HR sees in the new UI — legacy statuses on old rows are still
# accepted for backwards compatibility.
_NEW_STATUSES = (_DRAFT, _PUBLISHED, _APPROVED, _ARCHIVED)


# ── In-memory source-file store (small, single-process) ─────────────────────
#
# A future task can persist these to disk / S3. For now we keep the text
# in memory keyed by uuid so the agent can read it during generation. This
# matches the rest of the codebase's pragmatic "small upload" pattern.

_SOURCE_FILE_CACHE: dict[str, dict[str, str]] = {}


# ── Pydantic schemas ─────────────────────────────────────────────────────────


_ASSESSMENT_TYPE_TUPLE = ASSESSMENT_TYPES


class GenerateDraftRequest(BaseModel):
    job_id: str
    assessment_type: AssessmentType
    difficulty: Literal["junior", "intermediate", "senior", "expert"] | None = None
    question_count: int | None = Field(None, ge=1, le=25)
    duration_minutes: int | None = Field(None, ge=5, le=240)
    hr_instructions: str | None = None
    source_file_id: str | None = None
    candidate_instructions: str | None = None


class AssessmentApproveRequest(BaseModel):
    publish: bool = True  # accepts {publish: false} for "mark approved but not yet released"


class AssessmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    difficulty: str | None = None
    duration_minutes: int | None = None
    total_score: int | None = None
    instructions: str | None = None
    questions: list[dict[str, Any]] | None = None
    agent_metadata: dict[str, Any] | None = None
    # ── Legacy per-candidate-attempt fields kept for backwards compat ──
    score: float | None = None
    max_score: float | None = None
    reviewer_notes: str | None = None
    criteria_breakdown: dict[str, Any] | None = None
    submission_text: str | None = None
    submission_uri: str | None = None


class AssessmentCreate(BaseModel):
    """Legacy direct-create payload — kept so old callers still work.

    ``application_id`` and ``candidate_id`` are now OPTIONAL; new code
    should call ``POST /assessments/generate-draft`` instead.
    """

    job_id: str
    application_id: str | None = None
    candidate_id: str | None = None
    title: str = "Skills Assessment"
    assessment_type: str = "technical_assessment"
    difficulty: str | None = None
    duration_minutes: int | None = None
    total_score: int | None = None
    instructions: str | None = None
    max_score: float | None = None


class AssessmentOut(BaseModel):
    id: str
    organization_id: str
    job_id: str
    application_id: str | None
    candidate_id: str | None
    title: str
    description: str | None
    assessment_type: str
    difficulty: str | None
    duration_minutes: int | None
    total_score: int | None
    status: str
    questions: list[dict[str, Any]] | None
    agent_metadata: dict[str, Any] | None
    source_file_id: str | None
    source_file_name: str | None
    # Legacy attempt-side fields (still rendered by the old card UI).
    score: float | None
    max_score: float | None
    score_percent: float | None
    instructions: str | None
    submission_text: str | None
    submission_uri: str | None
    reviewer_notes: str | None
    criteria_breakdown: dict[str, Any] | None
    # Audit / workflow timestamps
    created_by: str | None
    approved_by: str | None
    approved_at: str | None
    assigned_at: str | None
    submitted_at: str | None
    reviewed_at: str | None
    created_at: str | None

    model_config = {"from_attributes": True}


class UploadSourceFileResponse(BaseModel):
    source_file_id: str
    source_file_name: str
    extracted_chars: int


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_out(a: Assessment) -> AssessmentOut:
    questions = a.questions if isinstance(a.questions, list) else None
    return AssessmentOut(
        id=str(a.id),
        organization_id=str(a.organization_id),
        job_id=str(a.job_id),
        application_id=str(a.application_id) if a.application_id else None,
        candidate_id=str(a.candidate_id) if a.candidate_id else None,
        title=a.title or "",
        description=a.description,
        assessment_type=a.assessment_type,
        difficulty=a.difficulty,
        duration_minutes=a.duration_minutes,
        total_score=a.total_score,
        status=a.status,
        questions=questions,
        agent_metadata=a.agent_metadata if isinstance(a.agent_metadata, dict) else None,
        source_file_id=str(a.source_file_id) if a.source_file_id else None,
        source_file_name=a.source_file_name,
        score=a.score,
        max_score=a.max_score,
        score_percent=a.score_percent,
        instructions=a.instructions,
        submission_text=a.submission_text,
        submission_uri=a.submission_uri,
        reviewer_notes=a.reviewer_notes,
        criteria_breakdown=a.criteria_breakdown if isinstance(a.criteria_breakdown, dict) else None,
        created_by=str(a.created_by) if a.created_by else None,
        approved_by=str(a.approved_by) if a.approved_by else None,
        approved_at=a.approved_at.isoformat() if a.approved_at else None,
        assigned_at=a.assigned_at.isoformat() if a.assigned_at else None,
        submitted_at=a.submitted_at.isoformat() if a.submitted_at else None,
        reviewed_at=a.reviewed_at.isoformat() if a.reviewed_at else None,
        created_at=a.created_at.isoformat() if a.created_at else None,
    )


def _load_org_job(db: Session, ctx: OrgContext, job_id_raw: str) -> Job:
    try:
        job_uuid = uuid.UUID(job_id_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_job_id") from exc
    job = db.get(Job, job_uuid)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.organization_id is not None and str(job.organization_id) != str(ctx.organization_id):
        raise HTTPException(status_code=403, detail="job_belongs_to_other_org")
    return job


# ── New endpoints (fix5.md primary flow) ────────────────────────────────────


@router.post("/generate-draft", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def generate_draft(
    body: GenerateDraftRequest,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Generate a job-level assessment draft via the LLM agent.

    Returns the persisted draft with ``status='draft'``. HR can then edit
    via PATCH and approve via :pyfunc:`approve_assessment`. The assessment
    is NOT visible to candidates until approved.
    """
    if body.assessment_type not in ASSESSMENT_TYPES:
        raise HTTPException(status_code=400, detail="invalid_assessment_type")

    job = _load_org_job(db, ctx, body.job_id)

    # Validation per fix5.md §12.
    if body.assessment_type == "technical_assessment":
        if not (job.requirements or job.description_text):
            raise HTTPException(
                status_code=400,
                detail="technical_assessment_requires_job_description_or_requirements",
            )
    if body.assessment_type == "hr_assessment":
        if not (body.hr_instructions and body.hr_instructions.strip()) and not body.source_file_id:
            raise HTTPException(
                status_code=400,
                detail="hr_assessment_requires_hr_instructions_or_source_file",
            )

    source_file_text: str | None = None
    source_file_name: str | None = None
    if body.source_file_id:
        cached = _SOURCE_FILE_CACHE.get(body.source_file_id)
        if not cached:
            raise HTTPException(status_code=404, detail="source_file_not_found")
        if str(cached.get("organization_id")) != str(ctx.organization_id):
            raise HTTPException(status_code=403, detail="source_file_belongs_to_other_org")
        source_file_text = cached.get("text") or ""
        source_file_name = cached.get("name")

    try:
        draft = generate_assessment_draft(
            job=job,
            assessment_type=body.assessment_type,
            difficulty=body.difficulty,
            question_count=body.question_count,
            duration_minutes=body.duration_minutes,
            hr_instructions=body.hr_instructions,
            source_file_text=source_file_text,
            source_file_name=source_file_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    assessment = Assessment(
        id=uuid.uuid4(),
        organization_id=ctx.organization_id,
        job_id=job.id,
        application_id=None,
        candidate_id=None,
        title=str(draft.get("title") or "Assessment Draft"),
        description=str(draft.get("description") or ""),
        assessment_type=body.assessment_type,
        difficulty=body.difficulty or "intermediate",
        duration_minutes=int(draft.get("duration_minutes") or body.duration_minutes or 45),
        total_score=int(draft.get("total_score") or 100),
        instructions=body.candidate_instructions,
        status=_DRAFT,
        questions=draft.get("questions") or [],
        agent_metadata=draft.get("agent_metadata") or {},
        source_file_id=uuid.UUID(body.source_file_id) if body.source_file_id else None,
        source_file_name=source_file_name,
        created_by=ctx.user.id if getattr(ctx, "user", None) and getattr(ctx.user, "id", None) else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return _to_out(assessment)


@router.post("/{assessment_id}/approve", response_model=AssessmentOut)
def approve_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentApproveRequest | None = None,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Flip a draft to ``published`` (or ``approved``) — candidates can now see it."""
    a = db.get(Assessment, assessment_id)
    if a is None or a.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="assessment_not_found")
    if a.status not in (_DRAFT, _APPROVED):
        raise HTTPException(
            status_code=400,
            detail=f"cannot_approve_status: {a.status}",
        )
    if not a.questions:
        raise HTTPException(status_code=400, detail="cannot_approve_empty_draft")

    publish = True if body is None else bool(body.publish)
    a.status = _PUBLISHED if publish else _APPROVED
    a.approved_at = datetime.now(timezone.utc)
    a.approved_by = ctx.user.id if getattr(ctx, "user", None) and getattr(ctx.user, "id", None) else None
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.post("/upload-source-file", response_model=UploadSourceFileResponse)
async def upload_source_file(
    file: UploadFile = File(...),
    ctx: OrgContext = Depends(require_active_org_status),
) -> UploadSourceFileResponse:
    """Accept a reference file (txt/md/json/csv/pdf-text/etc.) for the agent.

    The file is parsed best-effort to text and held in an in-memory cache
    keyed by a UUID the UI passes back to ``/generate-draft`` via
    ``source_file_id``. Binary formats we can't read inline raise 422 so
    the UI can surface a clear error.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="empty_file")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large_max_5mb")

    text = _safe_decode(raw, file.filename or "")
    if text is None:
        raise HTTPException(
            status_code=422,
            detail="unsupported_file_format_use_txt_md_csv_json_or_pdf_text",
        )

    sid = str(uuid.uuid4())
    _SOURCE_FILE_CACHE[sid] = {
        "organization_id": str(ctx.organization_id),
        "name": file.filename or "uploaded-file",
        "text": text,
    }
    # Cap cache to last 50 uploads per process to bound memory.
    if len(_SOURCE_FILE_CACHE) > 50:
        for k in list(_SOURCE_FILE_CACHE.keys())[:-50]:
            _SOURCE_FILE_CACHE.pop(k, None)
    return UploadSourceFileResponse(
        source_file_id=sid,
        source_file_name=file.filename or "uploaded-file",
        extracted_chars=len(text),
    )


def _safe_decode(raw: bytes, filename: str) -> str | None:
    """Best-effort text extraction. Returns None if we can't read it."""
    fn = filename.lower()
    if fn.endswith((".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".html", ".htm")):
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                return raw.decode(enc, errors="strict")[:60000]
            except UnicodeDecodeError:
                continue
    if fn.endswith(".pdf"):
        # Optional dependency — only if pypdf is installed.
        try:
            import pypdf  # type: ignore[import-untyped]
        except Exception:
            return None
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw))
            parts: list[str] = []
            for page in reader.pages[:50]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    continue
            text = "\n".join(parts).strip()
            return text[:60000] if text else None
        except Exception:
            return None
    # Best-effort plaintext fallback when extension is unknown.
    try:
        return raw.decode("utf-8", errors="strict")[:60000]
    except UnicodeDecodeError:
        return None


# ── Listing / get / patch / delete ──────────────────────────────────────────


@router.get("", response_model=list[AssessmentOut])
def list_assessments(
    application_id: str | None = Query(None),
    candidate_id: str | None = Query(None),
    job_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    assessment_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """List assessments scoped to the current organisation.

    Supports filtering by application/candidate (legacy callers), by
    ``job_id`` for the new job-level listing, by status, and by type.
    """
    q = select(Assessment).where(Assessment.organization_id == ctx.organization_id)
    if application_id:
        q = q.where(Assessment.application_id == uuid.UUID(application_id))
    if candidate_id:
        q = q.where(Assessment.candidate_id == uuid.UUID(candidate_id))
    if job_id:
        q = q.where(Assessment.job_id == uuid.UUID(job_id))
    if status_filter:
        q = q.where(Assessment.status == status_filter)
    if assessment_type:
        q = q.where(Assessment.assessment_type == assessment_type)
    q = q.order_by(Assessment.created_at.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return [_to_out(r) for r in rows]


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    a = db.get(Assessment, assessment_id)
    if a is None or a.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _to_out(a)


@router.patch("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentUpdate,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Edit a draft (or correct a legacy attempt row)."""
    a = db.get(Assessment, assessment_id)
    if a is None or a.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # ── New template fields ────────────────────────────────────────────
    if body.title is not None:
        a.title = body.title.strip() or a.title
    if body.description is not None:
        a.description = body.description
    if body.difficulty is not None:
        a.difficulty = body.difficulty
    if body.duration_minutes is not None:
        if body.duration_minutes < 5:
            raise HTTPException(status_code=400, detail="duration_minutes_minimum_5")
        a.duration_minutes = int(body.duration_minutes)
    if body.total_score is not None:
        a.total_score = int(body.total_score)
    if body.questions is not None:
        a.questions = body.questions
    if body.agent_metadata is not None:
        a.agent_metadata = body.agent_metadata
    if body.instructions is not None:
        a.instructions = body.instructions

    # ── Status transitions ─────────────────────────────────────────────
    if body.status is not None:
        before = a.status
        a.status = body.status
        if body.status in (_PUBLISHED, _APPROVED) and before == _DRAFT:
            a.approved_at = datetime.now(timezone.utc)
            a.approved_by = (
                ctx.user.id
                if getattr(ctx, "user", None) and getattr(ctx.user, "id", None)
                else None
            )
        # Legacy attempt timestamps
        if body.status == "submitted" and before != "submitted":
            a.submitted_at = datetime.now(timezone.utc)
        if body.status == "reviewed" and before != "reviewed":
            a.reviewed_at = datetime.now(timezone.utc)

    # ── Legacy per-candidate-attempt fields ────────────────────────────
    if body.score is not None:
        a.score = body.score
    if body.max_score is not None:
        a.max_score = body.max_score
    if body.score is not None and a.max_score and a.max_score > 0:
        a.score_percent = (body.score / a.max_score) * 100
    if body.reviewer_notes is not None:
        a.reviewer_notes = body.reviewer_notes
    if body.criteria_breakdown is not None:
        a.criteria_breakdown = body.criteria_breakdown
    if body.submission_text is not None:
        a.submission_text = body.submission_text
    if body.submission_uri is not None:
        a.submission_uri = body.submission_uri

    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: uuid.UUID,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    a = db.get(Assessment, assessment_id)
    if a is None or a.organization_id != ctx.organization_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    db.delete(a)
    db.commit()


@router.post("", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: AssessmentCreate,
    ctx: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Legacy direct-create endpoint kept for backwards compatibility.

    New UI flows must use ``POST /assessments/generate-draft``. This route
    no longer requires ``application_id`` / ``candidate_id``.
    """
    job = _load_org_job(db, ctx, body.job_id)
    a = Assessment(
        id=uuid.uuid4(),
        organization_id=ctx.organization_id,
        job_id=job.id,
        application_id=uuid.UUID(body.application_id) if body.application_id else None,
        candidate_id=uuid.UUID(body.candidate_id) if body.candidate_id else None,
        title=body.title or "Skills Assessment",
        assessment_type=body.assessment_type or "technical_assessment",
        difficulty=body.difficulty,
        duration_minutes=body.duration_minutes,
        total_score=body.total_score,
        status=_DRAFT,
        instructions=body.instructions,
        max_score=body.max_score,
        assigned_at=datetime.now(timezone.utc) if body.application_id else None,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


# ── Job-scoped routes (fix5.md §8) ──────────────────────────────────────────


@job_router.get("/{job_id}/assessments", response_model=list[AssessmentOut])
def list_job_assessments(
    job_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """HR-side: all job-level assessments (drafts + published)."""
    rows = db.execute(
        select(Assessment)
        .where(
            Assessment.organization_id == ctx.organization_id,
            Assessment.job_id == job_id,
        )
        .order_by(Assessment.created_at.desc())
        .limit(200),
    ).scalars().all()
    return [_to_out(r) for r in rows]


@job_router.get(
    "/{job_id}/published-assessments",
    response_model=list[AssessmentOut],
)
def list_published_job_assessments_for_candidate(
    job_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Only ``published`` assessments for a given job, scoped to the caller's org.

    Drafts are never returned. The job must belong to the caller's organisation
    — otherwise one company could read another company's assessments by passing
    a foreign job_id.
    """
    # 403 if the job belongs to a different organisation.
    _load_org_job(db, ctx, str(job_id))
    rows = db.execute(
        select(Assessment)
        .where(
            Assessment.job_id == job_id,
            Assessment.organization_id == ctx.organization_id,
            Assessment.status == _PUBLISHED,
        )
        .order_by(Assessment.approved_at.desc().nullslast(), Assessment.created_at.desc()),
    ).scalars().all()
    # Strip identity-leak fields not relevant to candidates and never include
    # legacy per-candidate-attempt rows that have an application_id (those
    # are not job-level templates).
    return [_to_out(r) for r in rows if r.application_id is None]


# ── Recruiter-side: per-candidate assessment results for a job ───────────────


class AssessmentResultOut(BaseModel):
    application_id: str
    candidate_id: str | None = None
    candidate_name: str | None = None
    current_title: str | None = None
    stage: str | None = None
    status: Literal["submitted", "not_started"] = "not_started"
    score: float | None = None
    max_score: float | None = None
    score_percent: float | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    provisional: bool = False
    submitted_at: str | None = None
    attempt_id: str | None = None


class AssessmentResultsOut(BaseModel):
    job_id: str
    has_assessment: bool
    template_title: str | None = None
    submitted_count: int = 0
    total_count: int = 0
    results: list[AssessmentResultOut] = Field(default_factory=list)


@job_router.get("/{job_id}/assessment-results", response_model=AssessmentResultsOut)
def list_job_assessment_results(
    job_id: str,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
):
    """Recruiter view: every candidate on this job + whether they took the
    assessment, their score and a short performance summary."""
    job = _load_org_job(db, ctx, job_id)

    template = db.execute(
        select(Assessment)
        .where(
            Assessment.job_id == job.id,
            Assessment.status == _PUBLISHED,
            Assessment.application_id.is_(None),
        )
        .order_by(Assessment.approved_at.desc().nullslast(), Assessment.created_at.desc())
        .limit(1)
    ).scalars().first()

    apps = db.execute(
        select(Application)
        .where(Application.job_id == job.id)
        .order_by(Application.created_at.desc())
    ).scalars().all()

    # Map application_id → graded attempt (per-candidate Assessment row).
    attempts = db.execute(
        select(Assessment).where(
            Assessment.job_id == job.id,
            Assessment.application_id.is_not(None),
        )
    ).scalars().all()
    attempt_by_app: dict[uuid.UUID, Assessment] = {}
    for att in attempts:
        if att.application_id is not None and att.application_id not in attempt_by_app:
            attempt_by_app[att.application_id] = att

    results: list[AssessmentResultOut] = []
    submitted = 0
    for app in apps:
        cand = db.get(Candidate, app.candidate_id) if app.candidate_id else None
        att = attempt_by_app.get(app.id)
        if att is not None:
            submitted += 1
            meta = att.agent_metadata if isinstance(att.agent_metadata, dict) else {}
            results.append(
                AssessmentResultOut(
                    application_id=str(app.id),
                    candidate_id=str(app.candidate_id) if app.candidate_id else None,
                    candidate_name=cand.full_name if cand else None,
                    current_title=cand.current_title if cand else None,
                    stage=app.current_stage_code,
                    status="submitted",
                    score=att.score,
                    max_score=att.max_score,
                    score_percent=att.score_percent,
                    summary=(meta.get("summary") if isinstance(meta, dict) else None) or att.reviewer_notes,
                    strengths=list(meta.get("strengths") or []) if isinstance(meta, dict) else [],
                    areas_to_improve=list(meta.get("areas_to_improve") or []) if isinstance(meta, dict) else [],
                    provisional=bool(meta.get("used_fallback")) if isinstance(meta, dict) else False,
                    submitted_at=att.submitted_at.isoformat() if att.submitted_at else None,
                    attempt_id=str(att.id),
                )
            )
        else:
            results.append(
                AssessmentResultOut(
                    application_id=str(app.id),
                    candidate_id=str(app.candidate_id) if app.candidate_id else None,
                    candidate_name=cand.full_name if cand else None,
                    current_title=cand.current_title if cand else None,
                    stage=app.current_stage_code,
                    status="not_started",
                )
            )

    # Submitted first (highest score), then not-started.
    results.sort(
        key=lambda r: (
            0 if r.status == "submitted" else 1,
            -(r.score_percent or 0.0),
        )
    )
    return AssessmentResultsOut(
        job_id=str(job.id),
        has_assessment=template is not None,
        template_title=template.title if template else None,
        submitted_count=submitted,
        total_count=len(apps),
        results=results,
    )
