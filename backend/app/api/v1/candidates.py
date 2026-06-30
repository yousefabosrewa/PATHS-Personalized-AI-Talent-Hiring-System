import calendar
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, delete, func

from app.core.candidate_access import org_can_view_candidate
from app.core.dependencies import (
    get_current_active_user,
    HIRING_STAFF_ROLE_CODES,
    oauth2_scheme,
)
from app.core.security import decode_access_token
from app.core.database import get_db
from app.db.models.application import Application, AuditEvent
from app.db.models.assessment import Assessment
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import (
    CandidateSkill,
    CandidateExperience,
    CandidateEducation,
    CandidateCertification,
    CandidateDocument,
)
from app.db.models.candidate_extras import CandidateLink
from app.db.models.decision_support import (
    DecisionEmail,
    DecisionSupportPacket,
    DevelopmentPlan,
)
from app.db.models.interview import (
    Interview,
    InterviewEvaluation,
    InterviewSummary,
)
from app.db.models.job import Job as JobModel
from app.db.models.screening import ScreeningResult, ScreeningRun
from app.db.models.scoring import CandidateJobScore
from app.db.models.user import User
from app.schemas.candidate import (
    CandidateProfileOut,
    CandidateProfileUpdateRequest,
    EducationItem,
    ExperienceItem,
    LinkItem,
    DocumentItem,
)
from app.services.learning_hub import LearningHubResponse, build_learning_hub
from app.services.assessment_agent.service import grade_submission
from app.services.decision_support.decision_support_service import deliver_email
from app.services.hiring_pipeline import (
    build_candidate_roadmap,
    pipeline_for_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/candidates", tags=["Candidates"])

def _profile_out(db: Session, cand: Candidate) -> CandidateProfileOut:
    """Build the full candidate profile: scalar columns + relational sections."""
    education = db.execute(
        select(CandidateEducation)
        .where(CandidateEducation.candidate_id == cand.id)
        .order_by(CandidateEducation.created_at)
    ).scalars().all()
    experiences = db.execute(
        select(CandidateExperience)
        .where(CandidateExperience.candidate_id == cand.id)
        .order_by(CandidateExperience.created_at)
    ).scalars().all()
    links = db.execute(
        select(CandidateLink)
        .where(CandidateLink.candidate_id == cand.id)
        .order_by(CandidateLink.created_at)
    ).scalars().all()
    documents = db.execute(
        select(CandidateDocument)
        .where(CandidateDocument.candidate_id == cand.id)
        .order_by(desc(CandidateDocument.created_at))
    ).scalars().all()
    return CandidateProfileOut(
        id=cand.id,
        full_name=cand.full_name,
        email=cand.email,
        other_emails=list(cand.other_emails or []),
        phone=cand.phone,
        location=cand.location_text,
        headline=cand.headline,
        current_title=cand.current_title,
        summary=cand.summary,
        years_experience=cand.years_experience,
        career_level=cand.career_level,
        skills=list(cand.skills or []),
        open_to_job_types=list(cand.open_to_job_types or []),
        open_to_workplace_settings=list(cand.open_to_workplace_settings or []),
        desired_job_titles=list(cand.desired_job_titles or []),
        desired_job_categories=list(cand.desired_job_categories or []),
        education=[EducationItem.model_validate(e) for e in education],
        experiences=[ExperienceItem.model_validate(x) for x in experiences],
        links=[LinkItem.model_validate(link) for link in links],
        documents=[DocumentItem.model_validate(d) for d in documents],
    )


@router.get("/me/profile", response_model=CandidateProfileOut)
async def get_my_candidate_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    return _profile_out(db, cand)


@router.put("/me/profile", response_model=CandidateProfileOut)
async def update_my_candidate_profile(
    body: CandidateProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    if body.full_name is not None:
        cand.full_name = body.full_name.strip()
        current_user.full_name = body.full_name.strip()
    if body.other_emails is not None:
        primary = (cand.email or "").strip().lower()
        seen: set[str] = set()
        cleaned: list[str] = []
        for raw in body.other_emails:
            e = (raw or "").strip().lower()
            # Keep it well-formed, drop blanks/dupes and the primary sign-in email.
            if not e or "@" not in e or e == primary or e in seen:
                continue
            seen.add(e)
            cleaned.append(e)
        cand.other_emails = cleaned[:10] or None
    if body.phone is not None:
        cand.phone = body.phone.strip() or None
    if body.location is not None:
        cand.location_text = body.location.strip() or None
    if body.current_title is not None:
        cand.current_title = body.current_title.strip() or None
    if body.summary is not None:
        cand.summary = body.summary.strip() or None
    if body.years_experience is not None:
        cand.years_experience = body.years_experience
    if body.career_level is not None:
        cand.career_level = body.career_level.strip() or None

    if body.skills is not None:
        cand.skills = [s.strip() for s in body.skills if s.strip()][:100]
    if body.open_to_job_types is not None:
        cand.open_to_job_types = [s.strip() for s in body.open_to_job_types if s.strip()][:10]
    if body.open_to_workplace_settings is not None:
        cand.open_to_workplace_settings = [
            s.strip() for s in body.open_to_workplace_settings if s.strip()
        ][:10]
    if body.desired_job_titles is not None:
        cand.desired_job_titles = [s.strip() for s in body.desired_job_titles if s.strip()][:10]
    if body.desired_job_categories is not None:
        cand.desired_job_categories = [
            s.strip() for s in body.desired_job_categories if s.strip()
        ][:20]

    # ── Relational sections — replace-all when provided ───────────────────
    # The frontend only sends a section when the candidate actually entered
    # rows for it, so a profile submit never wipes CV-extracted data.
    if body.education is not None:
        db.execute(delete(CandidateEducation).where(CandidateEducation.candidate_id == cand.id))
        for e in body.education:
            db.add(CandidateEducation(
                candidate_id=cand.id,
                institution=e.institution.strip(),
                degree=(e.degree or None),
                field_of_study=(e.field_of_study or None),
                start_date=(e.start_date or None),
                end_date=(e.end_date or None),
            ))
    if body.experiences is not None:
        db.execute(delete(CandidateExperience).where(CandidateExperience.candidate_id == cand.id))
        for x in body.experiences:
            db.add(CandidateExperience(
                candidate_id=cand.id,
                company_name=x.company_name.strip(),
                title=x.title.strip(),
                start_date=(x.start_date or None),
                end_date=(x.end_date or None),
                description=(x.description or None),
            ))
    if body.links is not None:
        db.execute(delete(CandidateLink).where(CandidateLink.candidate_id == cand.id))
        for link in body.links:
            db.add(CandidateLink(
                candidate_id=cand.id,
                link_type=link.link_type.strip(),
                url=link.url.strip(),
                label=(link.label or None),
            ))

    db.commit()
    db.refresh(cand)
    return _profile_out(db, cand)


# ── CV upload + extraction (onboarding step 1) ─────────────────────────────

_CV_ALLOWED_MIMES = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    b"\xd0\xcf\x11\xe0": "application/msword",
}
_CV_MAX_BYTES = 10 * 1024 * 1024


def _sniff_cv_mime(header: bytes) -> str | None:
    for magic, mime in _CV_ALLOWED_MIMES.items():
        if header.startswith(magic):
            return mime
    return None


def _extract_cv_sync(file_path: str) -> dict:
    """Run the CV-ingestion extraction nodes synchronously (no DB writes).

    Reuses the same text-extraction + LLM/regex structured extraction the async
    ingestion pipeline uses, but stops before persistence so we can hand the
    structured result straight back to the onboarding wizard for review.
    """
    from app.agents.cv_ingestion.nodes import (
        load_document,
        extract_structured_candidate_data,
        normalize_entities,
    )

    state: dict[str, Any] = {
        "job_id": "onboarding", "candidate_id": None, "document_id": None,
        "file_path": file_path, "raw_text": None, "structured_candidate": None,
        "normalized_candidate": None, "chunks": None, "embeddings": None,
        "errors": [], "status": "running", "stage": "started",
    }
    state.update(load_document(state))
    if state.get("status") == "failed":
        return {"_raw_text": None}
    state.update(extract_structured_candidate_data(state))
    state.update(normalize_entities(state))

    norm = state.get("normalized_candidate") or {}
    norm["_raw_text"] = state.get("raw_text")
    # Derive a current title from the most recent experience when absent.
    if not norm.get("current_title"):
        exps = norm.get("experiences") or []
        if exps and (exps[0].get("title") or "").strip() not in ("", "—"):
            norm["current_title"] = exps[0]["title"]
    return norm


@router.post("/me/cv-extract")
async def extract_my_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload the candidate's CV, extract structured data, and save the document.

    Returns the extracted basic info / contact / skills / experience / education
    so the onboarding wizard can pre-fill every step for the candidate to review.
    The CV file itself is stored as one of the candidate's documents.
    """
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    header = await file.read(8)
    mime = _sniff_cv_mime(header)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Only PDF and Word documents are accepted.",
        )
    rest = await file.read()
    data = header + rest
    if len(data) > _CV_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum is 10 MB.")

    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = file.filename or "cv"
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{safe_name}")
    with open(file_path, "wb") as f:
        f.write(data)

    # Extraction is blocking (PDF parse + LLM call) — run off the event loop.
    structured = await run_in_threadpool(_extract_cv_sync, file_path)

    skills = [
        (s.get("name") or "").strip()
        for s in (structured.get("skills") or [])
        if (s.get("name") or "").strip()
    ]

    # Pre-fill the candidate record so they become matchable to jobs straight
    # away (the dashboard "Top Matches" needs skills/title to rank). Skills are
    # merged (never replaced) and basic fields only fill when currently empty —
    # so this never clobbers anything the candidate later edits during review.
    if skills:
        merged = list(cand.skills or [])
        seen = {x.lower() for x in merged}
        for nm in skills:
            if nm.lower() not in seen:
                merged.append(nm)
                seen.add(nm.lower())
        cand.skills = merged[:100]
    if structured.get("current_title") and not cand.current_title:
        cand.current_title = str(structured["current_title"]).strip()[:255]
    if structured.get("summary") and not cand.summary:
        cand.summary = str(structured["summary"]).strip()
    if structured.get("location_text") and not cand.location_text:
        cand.location_text = str(structured["location_text"]).strip()[:255]
    if structured.get("years_experience") is not None and cand.years_experience is None:
        try:
            cand.years_experience = int(structured["years_experience"])
        except (TypeError, ValueError):
            pass

    # Persist the CV as one of the candidate's documents.
    doc = CandidateDocument(
        candidate_id=cand.id,
        document_type="cv",
        original_filename=safe_name,
        mime_type=mime,
        storage_path_or_url=file_path,
        raw_text=structured.get("_raw_text"),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "document_id": str(doc.id),
        "full_name": (structured.get("full_name") or "").strip() or None,
        "email": structured.get("email"),
        "phone": structured.get("phone"),
        "location": structured.get("location_text"),
        "summary": structured.get("summary"),
        "current_title": structured.get("current_title"),
        "years_experience": structured.get("years_experience"),
        "skills": skills,
        "experiences": structured.get("experiences") or [],
        "education": structured.get("education") or [],
        "certifications": structured.get("certifications") or [],
    }


@router.get("/me/applications")
async def get_my_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return applications submitted by the current candidate user."""
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    apps = db.execute(
        select(Application)
        .where(Application.candidate_id == cand.id)
        .order_by(desc(Application.created_at))
    ).scalars().all()

    # Assessment availability per application (batched — 2 queries total).
    job_ids = {app.job_id for app in apps if app.job_id}
    app_ids = {app.id for app in apps}
    jobs_with_template: set[uuid.UUID] = set()
    if job_ids:
        jobs_with_template = set(
            db.execute(
                select(Assessment.job_id).where(
                    Assessment.job_id.in_(job_ids),
                    Assessment.status == "published",
                    Assessment.application_id.is_(None),
                )
            ).scalars().all()
        )
    attempts_by_app: dict[uuid.UUID, Assessment] = {}
    if app_ids:
        for att in db.execute(
            select(Assessment).where(
                Assessment.candidate_id == cand.id,
                Assessment.application_id.in_(app_ids),
            )
        ).scalars().all():
            attempts_by_app[att.application_id] = att

    from app.services.candidate_job_match_service import candidate_job_match_score

    result = []
    for app in apps:
        job = app.job
        has_assessment = app.job_id in jobs_with_template
        match_score = None
        if job is not None:
            try:
                m = candidate_job_match_score(db, candidate_id=cand.id, job=job)
                match_score = m[0] if m else None
            except Exception:  # noqa: BLE001
                match_score = None
        attempt = attempts_by_app.get(app.id)
        assessment_status = (
            "submitted" if attempt is not None
            else "not_started" if has_assessment
            else "none"
        )
        roadmap = build_candidate_roadmap(
            pipeline_for_job(job) if job else [],
            app.current_stage_code,
            app.overall_status,
            has_match_score=bool((cand.skills or []) or cand.current_title),
        )
        result.append({
            "id": str(app.id),
            "job_id": str(app.job_id),
            "job_title": job.title if job else None,
            "company_name": job.company_name if job else None,
            "location_text": job.location_text if job else None,
            "workplace_type": job.workplace_type if job else None,
            "current_stage_code": app.current_stage_code,
            "overall_status": app.overall_status,
            "created_at": app.created_at.isoformat(),
            "match_score": match_score,
            "has_assessment": has_assessment,
            "assessment_status": assessment_status,
            "assessment_score_percent": (attempt.score_percent if attempt else None),
            "roadmap": roadmap,
        })
    return result


@router.get("/me/applications/{app_id}/fit")
def get_application_fit(
    app_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Candidate-facing transparency for the Applied + CV-Screening stages:
    their match to the job (matched / missing skills + explanation) and their
    CV-fit screening score with strengths and areas to strengthen."""
    from app.db.models.scoring import CandidateJobScore
    from app.services.candidate_job_match_service import candidate_job_match_score
    from app.services.decision_support.idss_context import _required_skills_from_job

    cand, app = _require_candidate_app(db, current_user, app_id)
    job = app.job
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found for this application.")

    match = candidate_job_match_score(db, candidate_id=cand.id, job=job)
    match_score = match[0] if match else None
    matched_skills = list(match[1]) if match else []

    cand_skills = {str(s).lower().strip() for s in (cand.skills or []) if isinstance(s, str)}
    try:
        required = _required_skills_from_job(db, job)
    except Exception:  # noqa: BLE001
        required = set()
    missing = sorted(required - cand_skills)[:8]

    cjs = db.execute(
        select(CandidateJobScore)
        .where(CandidateJobScore.candidate_id == cand.id, CandidateJobScore.job_id == job.id)
        .order_by(CandidateJobScore.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    cv_score = (
        float(cjs.final_score) if cjs is not None and cjs.final_score is not None
        else (float(match_score) if match_score is not None else None)
    )

    match_expl = (
        f"You match {len(matched_skills)} of this role's key skills"
        + (f": {', '.join(matched_skills[:6])}." if matched_skills else ".")
        + (f" Skills the role asks for that aren't on your profile yet: {', '.join(missing[:5])}." if missing else "")
    )
    if cv_score is not None:
        screening_expl = (
            f"Your CV scored {round(cv_score)}/100 for fit on this role. "
            + (f"What stood out: {', '.join(matched_skills[:5])}. " if matched_skills else "")
            + (f"To strengthen your fit, build evidence in: {', '.join(missing[:5])}." if missing else "")
        )
    else:
        screening_expl = "CV screening hasn't produced a score for this application yet."

    return {
        "application_id": str(app.id),
        "job_title": job.title,
        "match": {
            "score": round(float(match_score)) if match_score is not None else None,
            "matched_skills": matched_skills,
            "missing_skills": missing,
            "explanation": match_expl,
        },
        "screening": {
            "score": round(cv_score, 1) if cv_score is not None else None,
            "explanation": screening_expl,
            "strengths": matched_skills[:6],
            "gaps": missing,
        },
    }


# ── Candidate assessment flow ──────────────────────────────────────────────


class AssessmentSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


def _require_candidate_app(
    db: Session, current_user: User, app_id: uuid.UUID,
) -> tuple[Candidate, Application]:
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    app = db.get(Application, app_id)
    if app is None or app.candidate_id != cand.id:
        raise HTTPException(status_code=404, detail="Application not found")
    return cand, app


def _published_template(db: Session, job_id: uuid.UUID) -> Assessment | None:
    return db.execute(
        select(Assessment)
        .where(
            Assessment.job_id == job_id,
            Assessment.status == "published",
            Assessment.application_id.is_(None),
        )
        .order_by(Assessment.approved_at.desc().nullslast(), Assessment.created_at.desc())
        .limit(1)
    ).scalars().first()


def _attempt_for(
    db: Session, app_id: uuid.UUID, candidate_id: uuid.UUID,
) -> Assessment | None:
    return db.execute(
        select(Assessment)
        .where(
            Assessment.application_id == app_id,
            Assessment.candidate_id == candidate_id,
        )
        .order_by(Assessment.created_at.desc())
        .limit(1)
    ).scalars().first()


def _candidate_question_view(q: dict, idx: int) -> dict:
    """Candidate-safe question — strips expected_answer / rubric / correct_answer."""
    return {
        "id": str(q.get("id") or idx),
        "question": q.get("question"),
        "scenario": q.get("scenario"),
        "type": q.get("type"),
        "options": q.get("options") if isinstance(q.get("options"), list) else None,
        "score": q.get("score"),
        "estimated_time_minutes": q.get("estimated_time_minutes"),
        "difficulty": q.get("difficulty"),
    }


def _attempt_report(att: Assessment) -> dict:
    meta = att.agent_metadata if isinstance(att.agent_metadata, dict) else {}
    breakdown = att.criteria_breakdown if isinstance(att.criteria_breakdown, dict) else {}
    return {
        "status": "submitted",
        "score": att.score,
        "max_score": att.max_score,
        "score_percent": att.score_percent,
        "summary": meta.get("summary") or att.reviewer_notes,
        "strengths": meta.get("strengths") or [],
        "areas_to_improve": meta.get("areas_to_improve") or [],
        "per_question": breakdown.get("per_question") or [],
        "submitted_at": att.submitted_at.isoformat() if att.submitted_at else None,
        "provisional": bool(meta.get("used_fallback")),
    }


def _notify_tutor(db: Session, *, template: Assessment, job, cand: Candidate, report: dict) -> None:
    """Email the assessment's owner (tutor) the submission summary + answers."""
    try:
        tutor_id = template.created_by or (job.created_by_user_id if job else None)
        tutor = db.get(User, tutor_id) if tutor_id else None
        if tutor is None or not tutor.email:
            return
        pct = report["score_percent"]
        lines = [
            f"{cand.full_name or 'A candidate'} has completed the assessment "
            f'"{template.title}" for {job.title if job else "the role"}.',
            "",
            f"Score: {report['total_score']:.0f} / {report['max_score']:.0f} ({pct:.0f}%)",
            "",
            f"Summary: {report['summary']}",
        ]
        if report.get("strengths"):
            lines += ["", "Strengths:"] + [f"  - {s}" for s in report["strengths"]]
        if report.get("areas_to_improve"):
            lines += ["", "Areas to improve:"] + [f"  - {s}" for s in report["areas_to_improve"]]
        lines += ["", "Answers & per-question grading:"]
        for i, pq in enumerate(report.get("per_question") or [], start=1):
            lines += [
                "",
                f"Q{i}. {pq.get('question', '')}",
                f"Answer: {pq.get('answer') or '(blank)'}",
                f"Score: {pq.get('awarded', 0):.0f}/{pq.get('max', 0):.0f} - {pq.get('feedback', '')}",
            ]
        deliver_email(
            db,
            to=tutor.email,
            subject=(
                f"Assessment submitted: {cand.full_name or 'Candidate'} "
                f"- {pct:.0f}% ({template.title})"
            ),
            body="\n".join(lines),
            hr_user_id=tutor_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[Assessment] tutor notification failed")


# Canonical pipeline order — the assessment is locked until the candidate
# reaches the assessment stage (rank >= 2).
_ASSESSMENT_STAGE_RANK: dict[str, int] = {
    "applied": 0, "sourced": 0,
    "screening": 1, "screen": 1,
    "assessment": 2,
    "interview": 3, "hr_interview": 3, "tech_interview": 3, "mixed_interview": 3,
    "decision": 4, "evaluate": 4, "offer": 4, "offered": 4,
    "hired": 5, "accepted": 5,
}


def _reached_assessment_stage(app) -> bool:
    """True once the application has reached (or passed) the assessment stage."""
    code = (app.current_stage_code or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ASSESSMENT_STAGE_RANK.get(code, 0) >= 2


@router.get("/me/applications/{app_id}/assessment")
async def get_application_assessment(
    app_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """One application's assessment for the candidate: the questions to answer
    (answer keys stripped) and, once submitted, their graded report."""
    cand, app = _require_candidate_app(db, current_user, app_id)
    job = app.job
    template = _published_template(db, app.job_id) if app.job_id else None
    attempt = _attempt_for(db, app.id, cand.id)

    # Locked until the candidate reaches the assessment stage. A candidate who
    # already submitted keeps access to their report regardless of stage.
    if template is not None and attempt is None and not _reached_assessment_stage(app):
        return {
            "application_id": str(app.id),
            "job_id": str(app.job_id) if app.job_id else None,
            "job_title": job.title if job else None,
            "available": False,
            "locked": True,
            "status": "locked",
            "locked_reason": (
                "This assessment unlocks once you reach the assessment stage."
            ),
            "assessment": None,
            "report": None,
        }

    payload: dict = {
        "application_id": str(app.id),
        "job_id": str(app.job_id) if app.job_id else None,
        "job_title": job.title if job else None,
        "available": template is not None,
        "status": "submitted" if attempt is not None else "not_started",
        "assessment": None,
        "report": _attempt_report(attempt) if attempt is not None else None,
    }
    if template is not None:
        questions = template.questions if isinstance(template.questions, list) else []
        payload["assessment"] = {
            "id": str(template.id),
            "title": template.title,
            "description": template.description,
            "assessment_type": template.assessment_type,
            "difficulty": template.difficulty,
            "duration_minutes": template.duration_minutes,
            "total_score": template.total_score,
            "instructions": template.instructions,
            "questions": [
                _candidate_question_view(q, i)
                for i, q in enumerate(questions)
                if isinstance(q, dict)
            ],
        }
    return payload


@router.post("/me/applications/{app_id}/assessment/submit")
async def submit_application_assessment(
    app_id: uuid.UUID,
    body: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Grade the answers, store the attempt, notify the tutor, and return the
    candidate's performance report."""
    cand, app = _require_candidate_app(db, current_user, app_id)
    template = _published_template(db, app.job_id) if app.job_id else None
    if template is None:
        raise HTTPException(
            status_code=404,
            detail="No assessment is available for this application.",
        )

    existing = _attempt_for(db, app.id, cand.id)
    if existing is not None:
        # Idempotent — return the existing report instead of double-grading.
        return _attempt_report(existing)

    # Can't take an assessment before reaching the assessment stage.
    if not _reached_assessment_stage(app):
        raise HTTPException(
            status_code=403,
            detail="This assessment is not available yet — you have not reached the assessment stage.",
        )

    questions = template.questions if isinstance(template.questions, list) else []
    job = app.job
    report = grade_submission(
        questions=questions,
        answers={str(k): str(v) for k, v in (body.answers or {}).items()},
        job_title=job.title if job else None,
    )

    now = datetime.now(timezone.utc)
    attempt = Assessment(
        organization_id=template.organization_id,
        job_id=template.job_id,
        application_id=app.id,
        candidate_id=cand.id,
        title=template.title,
        description=template.description,
        assessment_type=template.assessment_type,
        difficulty=template.difficulty,
        duration_minutes=template.duration_minutes,
        total_score=int(report["max_score"]) if report.get("max_score") else None,
        status="reviewed",
        questions=questions,
        score=report["total_score"],
        max_score=report["max_score"],
        score_percent=report["score_percent"],
        reviewer_notes=report["summary"],
        criteria_breakdown={"per_question": report["per_question"]},
        agent_metadata={
            "answers": body.answers,
            "summary": report["summary"],
            "strengths": report["strengths"],
            "areas_to_improve": report["areas_to_improve"],
            "used_fallback": report["used_fallback"],
            "graded_by": "assessment_grader_v1",
        },
        created_by=cand.user_id,
        assigned_at=template.approved_at,
        submitted_at=now,
        reviewed_at=now,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    _notify_tutor(db, template=template, job=job, cand=cand, report=report)
    return _attempt_report(attempt)


@router.get("/me/applications/{app_id}/journey")
def get_application_journey(
    app_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Candidate-facing per-stage analysis for a FINALISED application.

    Once a hiring decision is recorded (accepted / rejected), the candidate can
    open the job and see each stage of this job's pipeline — their score, the AI
    explanation and the result — plus the decision message and development plan,
    so they understand exactly why. Internal HR notes are NEVER exposed here.
    Before a final decision, the analysis stays locked (``finalized=false``).
    """
    from types import SimpleNamespace

    from app.services.decision_support.per_stage import build_per_stage_breakdown

    cand, app = _require_candidate_app(db, current_user, app_id)
    job = app.job
    status = (app.overall_status or "").lower()
    stage = (app.current_stage_code or "").lower()
    if "accepted" in status or stage == "hired":
        decision = "accepted"
    elif "rejected" in status or stage == "rejected":
        decision = "rejected"
    else:
        decision = None

    payload: dict[str, Any] = {
        "application_id": str(app.id),
        "job_id": str(app.job_id) if app.job_id else None,
        "job_title": job.title if job else None,
        "finalized": decision is not None,
        "decision": decision,
        "overall": {"score": None, "recommendation": None},
        "stages": [],
        "decision_message": None,
        "development_plan": None,
    }
    if decision is None:
        return payload  # analysis unlocks only once a final decision exists

    packet = db.execute(
        select(DecisionSupportPacket)
        .where(
            DecisionSupportPacket.candidate_id == cand.id,
            DecisionSupportPacket.job_id == app.job_id,
        )
        .order_by(DecisionSupportPacket.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    shim = packet or SimpleNamespace(
        job_id=app.job_id, candidate_id=cand.id, packet_json={},
    )
    stages = build_per_stage_breakdown(db, shim)
    for st in stages:
        st.pop("hr_notes", None)  # internal recruiter notes — never shown to the candidate
    payload["stages"] = stages

    if packet is not None:
        payload["overall"] = {
            "score": packet.final_journey_score,
            "recommendation": packet.recommendation,
        }
        email = db.execute(
            select(DecisionEmail)
            .where(DecisionEmail.decision_packet_id == packet.id)
            .order_by(DecisionEmail.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if email is not None and (email.status or "").lower() == "sent":
            payload["decision_message"] = email.body
        plan = db.execute(
            select(DevelopmentPlan)
            .where(DevelopmentPlan.decision_packet_id == packet.id)
            .order_by(DevelopmentPlan.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if plan is not None:
            payload["development_plan"] = {
                "plan_type": plan.plan_type,
                "summary": plan.summary,
            }
    return payload


@router.post("/me/jobs/{job_id}/apply", status_code=201)
async def apply_to_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Candidate submits a direct application for a job.

    Returns 201 on success, 403 for wrong role, 404 for missing profile/job,
    409 when already applied.
    """
    if current_user.account_type != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidate accounts can apply for jobs",
        )

    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found. Please complete your profile first.",
        )

    # Verify the job exists and is accepting applications
    job = db.get(JobModel, job_id)
    if not job or not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or no longer accepting applications",
        )

    # External scraped jobs: redirect candidate to original posting
    app_mode = getattr(job, "application_mode", "internal_apply")
    if app_mode == "external_redirect":
        ext_url = job.external_apply_url or job.source_url
        if not ext_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This external job has no apply URL configured",
            )
        return {
            "external_apply_url": ext_url,
            "message": "This job is hosted externally. Redirecting to original posting.",
        }

    # Duplicate check — 409 Conflict
    existing = db.execute(
        select(Application).where(
            Application.candidate_id == cand.id,
            Application.job_id == job_id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied for this job",
        )

    new_app = Application(
        candidate_id=cand.id,
        job_id=job_id,
        application_type="direct",
        source_channel="candidate_portal",
        current_stage_code="applied",
        overall_status="active",
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {
        "id": str(new_app.id),
        "job_id": str(job_id),
        "stage": "applied",
        "message": "Application submitted successfully",
    }


@router.get("/me/jobs/{job_id}/application-status")
async def get_job_application_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Check whether the current candidate has already applied to a job."""
    if current_user.account_type != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidate accounts can check application status",
        )

    cand = current_user.candidate_profile
    if not cand:
        return {"applied": False, "application_id": None, "stage": None}

    existing = db.execute(
        select(Application).where(
            Application.candidate_id == cand.id,
            Application.job_id == job_id,
        )
    ).scalar_one_or_none()

    if existing:
        return {
            "applied": True,
            "application_id": str(existing.id),
            "stage": existing.current_stage_code,
        }

    return {"applied": False, "application_id": None, "stage": None}


def _ensure_can_read_candidate(
    db: Session,
    current_user: User,
    bearer_token: str,
    cand_uuid: uuid.UUID,
) -> None:
    if current_user.account_type == "candidate":
        own = current_user.candidate_profile
        if not own or own.id != cand_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to view this candidate",
            )
        return
    if current_user.account_type != "organization_member":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to view this candidate",
        )
    payload = decode_access_token(bearer_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    role = payload.get("role_code") or ""
    if role not in HIRING_STAFF_ROLE_CODES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires a recruiter, HR, or hiring manager role",
        )
    org_id_raw = payload.get("organization_id")
    if not org_id_raw:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization in token")
    org_id = uuid.UUID(org_id_raw)
    if not org_can_view_candidate(db, org_id, cand_uuid):
        raise HTTPException(status_code=404, detail="Candidate not found")


def _should_mask_candidate_identity(
    db: Session,
    current_user: User,
    cand_uuid: uuid.UUID,
) -> bool:
    """Return True when this caller must see a masked (anonymized) identity.

    Candidate.md §2 — masking is enforced server-side: an organisation user
    only sees real identity after an approved de-anonymization request for
    this candidate in their org. A candidate viewing their own profile is
    never masked.
    """
    if current_user.account_type != "organization_member":
        return False
    member = next(iter(current_user.memberships or []), None)
    if member is None:
        return False
    from app.db.models.bias_fairness import DeAnonEvent

    granted = db.execute(
        select(DeAnonEvent)
        .where(
            DeAnonEvent.candidate_id == cand_uuid,
            DeAnonEvent.org_id == member.organization_id,
            DeAnonEvent.granted_at.is_not(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    return granted is None


@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    bearer_token: str = Depends(oauth2_scheme),
):
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate_id UUID")

    _ensure_can_read_candidate(db, current_user, bearer_token, cand_uuid)

    cand = db.get(Candidate, cand_uuid)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    skills = db.execute(select(CandidateSkill).where(CandidateSkill.candidate_id == cand_uuid)).scalars().all()
    experiences = db.execute(select(CandidateExperience).where(CandidateExperience.candidate_id == cand_uuid)).scalars().all()
    education = db.execute(select(CandidateEducation).where(CandidateEducation.candidate_id == cand_uuid)).scalars().all()
    certifications = db.execute(select(CandidateCertification).where(CandidateCertification.candidate_id == cand_uuid)).scalars().all()

    # Candidate.md §2 — backend-enforced identity masking. Organisation users
    # (recruiters / HR) only see a candidate's real identity once a
    # de-anonymization request for that candidate has been approved. The
    # candidate viewing their own profile is never masked.
    mask_identity = _should_mask_candidate_identity(db, current_user, cand_uuid)
    if mask_identity:
        full_name = f"Candidate {str(cand.id).replace('-', '')[:6].upper()}"
        email = None
        phone = None
        location_text = None
    else:
        full_name = cand.full_name
        email = cand.email
        phone = cand.phone
        location_text = cand.location_text

    return {
        "candidate": {
            "id": str(cand.id),
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "location_text": location_text,
            "is_anonymized": mask_identity,
            "current_title": cand.current_title,
            "headline": cand.headline,
            "summary": cand.summary,
            "years_experience": cand.years_experience,
            "career_level": cand.career_level,
            "skills": list(cand.skills or []),
            "open_to_job_types": list(cand.open_to_job_types or []),
            "open_to_workplace_settings": list(cand.open_to_workplace_settings or []),
            "desired_job_titles": list(cand.desired_job_titles or []),
            "desired_job_categories": list(cand.desired_job_categories or []),
        },
        "skills": [{"skill_id": str(s.skill_id), "score": s.proficiency_score} for s in skills],
        "experiences": [{"company": e.company_name, "title": e.title} for e in experiences],
        "education": [{"institution": e.institution, "degree": e.degree} for e in education],
        "certifications": [{"name": c.name, "issuer": c.issuer} for c in certifications]
    }


@router.get("/{candidate_id}/profile")
async def get_candidate_profile_detail(
    candidate_id: str,
    job_id: str | None = Query(default=None, description="Include scores for this job"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    bearer_token: str = Depends(oauth2_scheme),
):
    """Full candidate profile: CV + score breakdown + activity timeline."""
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate_id UUID")

    _ensure_can_read_candidate(db, current_user, bearer_token, cand_uuid)

    cand = db.get(Candidate, cand_uuid)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # CV layers
    experiences = db.execute(
        select(CandidateExperience)
        .where(CandidateExperience.candidate_id == cand_uuid)
        .order_by(desc(CandidateExperience.start_date))
    ).scalars().all()

    education = db.execute(
        select(CandidateEducation)
        .where(CandidateEducation.candidate_id == cand_uuid)
    ).scalars().all()

    skills = db.execute(
        select(CandidateSkill).where(CandidateSkill.candidate_id == cand_uuid)
    ).scalars().all()

    certifications = db.execute(
        select(CandidateCertification).where(CandidateCertification.candidate_id == cand_uuid)
    ).scalars().all()

    # Scores (for a specific job context if provided)
    scores = []
    overall_score = None
    pipeline_stage = None

    if job_id:
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid job_id UUID")

        score_row = db.execute(
            select(CandidateJobScore)
            .where(
                CandidateJobScore.candidate_id == cand_uuid,
                CandidateJobScore.job_id == job_uuid,
            )
            .order_by(desc(CandidateJobScore.scored_at))
            .limit(1)
        ).scalar_one_or_none()

        if score_row:
            overall_score = float(score_row.final_score)
            breakdown = score_row.criteria_breakdown or {}
            for criterion, detail in breakdown.items():
                if isinstance(detail, dict):
                    scores.append({
                        "criterion": criterion,
                        "score": detail.get("score"),
                        "weight": detail.get("weight"),
                        "reasoning": detail.get("reasoning"),
                    })

        app_row = db.execute(
            select(Application)
            .where(Application.candidate_id == cand_uuid, Application.job_id == job_uuid)
            .limit(1)
        ).scalar_one_or_none()
        if app_row:
            pipeline_stage = app_row.pipeline_stage

    # Activity timeline from audit_events
    activity_rows = db.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_id == str(cand_uuid))
        .order_by(desc(AuditEvent.created_at))
        .limit(20)
    ).scalars().all()

    activity = [
        {
            "type": row.action,
            "at": row.created_at.isoformat(),
            "actor": row.actor_id,
            "payload": row.after_jsonb or {},
        }
        for row in activity_rows
    ]

    return {
        "id": str(cand.id),
        "name": cand.full_name,
        "headline": cand.headline,
        "location": cand.location_text,
        "email_masked": (cand.email[:3] + "***@***" + cand.email.split("@")[-1][-4:]) if cand.email else None,
        "phone_masked": ("***-***-" + cand.phone[-4:]) if cand.phone else None,
        "current_role": cand.current_title,
        "years_experience": cand.years_experience,
        "overall_score": overall_score,
        "pipeline_stage": pipeline_stage,
        "cv": {
            "experience": [
                {
                    "company": e.company_name,
                    "title": e.title,
                    "start_date": e.start_date.isoformat() if e.start_date else None,
                    "end_date": e.end_date.isoformat() if e.end_date else None,
                    "description": e.description,
                }
                for e in experiences
            ],
            "education": [
                {
                    "institution": e.institution,
                    "degree": e.degree,
                    "field": e.field_of_study,
                    "graduation_year": e.graduation_year,
                }
                for e in education
            ],
            "skills": [{"skill_id": str(s.skill_id), "proficiency": s.proficiency_score} for s in skills],
            "certifications": [{"name": c.name, "issuer": c.issuer} for c in certifications],
        },
        "scores": scores,
        "activity": activity,
    }


@router.get("/{candidate_id}/learning-hub", response_model=LearningHubResponse)
async def get_candidate_learning_hub(
    candidate_id: str,
    target_role: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    bearer_token: str = Depends(oauth2_scheme),
):
    """Personalised Learning Hub recommendations (roadmap.sh) for a candidate.

    Connects recruitment data — current role, skills, skill gaps, interests,
    and applied jobs — to a tailored career-development plan. Accessible to
    the candidate themselves and to hiring staff allowed to view them
    (same authorisation rule as the candidate profile endpoints).
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate_id UUID")

    _ensure_can_read_candidate(db, current_user, bearer_token, cand_uuid)

    cand = db.get(Candidate, cand_uuid)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return build_learning_hub(db, cand, target_role_override=target_role)


# ── Candidate-owned document delete ─────────────────────────────────────────


@router.delete("/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a CV / document the candidate uploaded.

    Removes the database row AND the file on disk. Profile data the CV
    ingestion agent extracted (skills, experiences, education, links, …)
    lives in separate tables and is intentionally NOT touched here.
    """
    cand = db.execute(
        select(Candidate).where(Candidate.user_id == current_user.id)
    ).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    doc = db.execute(
        select(CandidateDocument).where(
            CandidateDocument.id == document_id,
            CandidateDocument.candidate_id == cand.id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Best-effort file delete — if the file is already missing or the path is
    # unset, still drop the DB row so the UI matches reality.
    path = doc.storage_path_or_url
    if path and os.path.isfile(path):
        try:
            os.unlink(path)
        except OSError as exc:  # noqa: BLE001
            logger.warning("Could not delete CV file '%s': %s", path, exc)

    db.delete(doc)
    db.commit()
    return None


# ────────────────────────────────────────────────────────────────────────────
# fix2.md §3 / §4 / §5 — Candidate CSV import (no job context required)
#
# Consolidates the "bring candidates in" flows that used to live in three
# separate places (Candidate Sources, CV Processing, Duplicate Candidates).
# Recruiters now drop a CSV into Candidates → Sources and the existing
# ``import_candidates_from_csv`` service handles:
#   • column normalization (name/email/title/linkedin/github/cv_url/...)
#   • CV-link download + ingestion through the LangGraph CV pipeline
#   • duplicate detection by email/linkedin/github
#   • vectorization + full sync (Postgres + Qdrant + graph)
# ────────────────────────────────────────────────────────────────────────────

from fastapi import File, Form, UploadFile  # noqa: E402
from app.db.repositories import organization_matching_repo as _omr  # noqa: E402
from app.services.organization_matching.organization_csv_candidate_import_service import (  # noqa: E402
    import_candidates_from_csv as _import_candidates_from_csv,
)


@router.post("/import-csv", status_code=200)
async def import_candidates_csv(
    csv_file: UploadFile = File(...),
    source_type: str = Form("company_uploaded"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Bulk-import candidates from a CSV (fix2.md §3).

    Accepts a CSV with at least a ``cv_url`` column.  Optional columns are
    column-normalized inside the import service (``email``, ``full_name``,
    ``linkedin_url``, ``github_url``, etc.).  Each row creates or updates a
    candidate profile through the existing ingestion pipeline — no parallel
    code path.

    ``source_type`` is recorded on every newly-created candidate so the UI
    can tag job-fair imports (§5) with a visible "Job Fair" badge.  Values:
    ``company_uploaded`` (default), ``job_fair``.

    Tenant scope is taken from the caller's JWT — clients never pass an
    organization_id.
    """
    # Resolve the caller's organisation membership.  This is the same path
    # the rest of the recruiter API uses — it raises 403 for candidate
    # accounts and ensures the org is active.
    if current_user.account_type == "candidate":
        raise HTTPException(403, detail="Only hiring staff can import candidates")
    member = next(iter(current_user.memberships or []), None)
    if member is None:
        raise HTTPException(403, detail="No organisation membership found")
    organization_id = member.organization_id

    raw = await csv_file.read()
    # The CSV import service writes error rows that FK-reference both the
    # matching_run and the import bookkeeping rows.  Create both up front
    # so the FK constraints never fire mid-import.  The matching run is
    # tagged ``path_type=csv_candidate_list`` so it doesn't pollute the
    # job-level matching dashboards (those filter on path_type).
    run = _omr.create_matching_run(
        db,
        {
            "organization_id": organization_id,
            "path_type": "csv_candidate_list",
            "top_k": 0,  # no scoring — this is a pure import
            "status": "running",
        },
    )
    matching_run_id = run.id
    import_row = _omr.create_candidate_import(
        db,
        {
            "organization_id": organization_id,
            "matching_run_id": matching_run_id,
            "file_name": csv_file.filename or "candidates.csv",
            "status": "running",
            "metadata": {"source_type": (source_type or "company_uploaded").strip().lower()},
        },
    )
    import_id = import_row.id
    db.commit()

    try:
        result = _import_candidates_from_csv(
            db,
            organization_id=organization_id,
            matching_run_id=matching_run_id,
            import_id=import_id,
            file_bytes=raw,
            _file_name=csv_file.filename or "candidates.csv",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CandidateCSVImport] failed")
        raise HTTPException(500, detail=f"import_failed: {exc}") from exc

    return {
        "ok": True,
        "import_id": str(import_id),
        "source_type": (source_type or "company_uploaded").strip().lower(),
        "total_rows":        result.get("total_rows", 0),
        "valid_rows":        result.get("valid_rows", 0),
        "imported":          result.get("imported_candidates", 0),
        "updated":           result.get("updated_candidates", 0),
        "failed":            result.get("failed_rows", 0),
        "candidate_ids":     result.get("candidate_ids", []),
    }


@router.get("/incomplete", status_code=200)
def list_incomplete_profiles(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List candidates whose profile is missing important fields (fix2.md §7).

    "Missing important fields" = no skills OR no experience OR no CV doc OR
    no LinkedIn link OR no GitHub link OR no phone OR no current title.

    Returns each candidate with a `missing` array listing exactly what is
    absent, plus a `completion` score 0-100 so the UI can show a progress
    badge.  Excludes candidates whose profile is already complete.
    """
    if current_user.account_type == "candidate":
        raise HTTPException(403, detail="Only hiring staff can browse this view")
    member = next(iter(current_user.memberships or []), None)
    if member is None:
        raise HTTPException(403, detail="No organisation membership found")

    # Pull every candidate the org can see.  We bound at `limit` rows
    # after filtering, so the page never explodes.
    candidates = list(
        db.execute(
            select(Candidate)
            .order_by(desc(Candidate.updated_at), desc(Candidate.created_at))
            .limit(limit * 4)  # extra headroom — many will be filtered out as "complete"
        ).scalars().all()
    )

    items: list[dict] = []
    for c in candidates:
        if len(items) >= limit:
            break
        # Honour tenant isolation for non-PATHS-profile candidates.
        try:
            if not org_can_view_candidate(db, member.organization_id, c.id):
                continue
        except Exception:  # noqa: BLE001
            continue

        # Probe each "important" field. Each entry is (field_label, present).
        has_skills      = db.execute(
            select(CandidateSkill.id).where(CandidateSkill.candidate_id == c.id).limit(1)
        ).scalar() is not None
        has_experience  = db.execute(
            select(CandidateExperience.id).where(CandidateExperience.candidate_id == c.id).limit(1)
        ).scalar() is not None
        has_education   = db.execute(
            select(CandidateEducation.id).where(CandidateEducation.candidate_id == c.id).limit(1)
        ).scalar() is not None
        has_cv_doc      = db.execute(
            select(CandidateDocument.id).where(CandidateDocument.candidate_id == c.id).limit(1)
        ).scalar() is not None
        links = list(
            db.execute(
                select(CandidateLink.platform).where(CandidateLink.candidate_id == c.id)
            ).scalars().all()
        )
        link_platforms = {str(p).lower() for p in links if p}
        has_linkedin = "linkedin" in link_platforms
        has_github   = "github" in link_platforms

        missing: list[str] = []
        if not (c.email or "").strip():     missing.append("Email")
        if not (c.phone or "").strip():     missing.append("Phone")
        if not (getattr(c, "current_title", None) or "").strip():
            missing.append("Current position")
        if not has_cv_doc:                  missing.append("CV")
        if not has_skills:                  missing.append("Skills")
        if not has_experience:              missing.append("Experience")
        if not has_education:               missing.append("Education")
        if not has_linkedin:                missing.append("LinkedIn")
        if not has_github:                  missing.append("GitHub")

        # 9 fields total — completion is a simple fraction of fields present.
        TOTAL = 9
        present_count = TOTAL - len(missing)
        completion = round(100 * present_count / TOTAL)

        if not missing:
            # Profile is complete — skip it.  This view is *only* about
            # candidates that still need attention.
            continue

        items.append({
            "candidate_id":   str(c.id),
            "name":           c.full_name or "",
            "email":          c.email or "",
            "source":         getattr(c, "source", None) or getattr(c, "source_type", None) or "",
            "current_title":  getattr(c, "current_title", "") or "",
            "missing":        missing,
            "completion":     completion,
        })

    return {"items": items, "total": len(items)}


# ────────────────────────────────────────────────────────────────────────────
# fix3.md §5 — Preparation Agent endpoint
#
# Generates one of four AI-assisted artifacts for a recruiter:
#   pre_analysis | technical_questions | hr_questions | assessment
# Identity is always anonymized — the agent receives only the candidate
# alias + structured evidence, never the real name / email / photo.
# ────────────────────────────────────────────────────────────────────────────

from typing import Any, Literal  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from app.services.preparation import (  # noqa: E402
    generate_preparation,
    get_preparation_drafts,
    save_preparation_draft,
)


class PreparationGenerateBody(BaseModel):
    output_type: Literal[
        "pre_analysis", "technical_questions", "hr_questions", "assessment",
    ]
    job_id: uuid.UUID | None = None


class PreparationGenerateOut(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID | None = None
    output_type: str
    content: dict[str, Any]


@router.post(
    "/{candidate_id}/preparation/generate",
    response_model=PreparationGenerateOut,
)
def preparation_generate(
    candidate_id: uuid.UUID,
    body: PreparationGenerateBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Run the Preparation Agent for one of the four output types
    (fix3.md §5).  Only hiring staff can call this.  The candidate is
    NEVER identified by real name in the agent prompt."""
    if current_user.account_type == "candidate":
        raise HTTPException(403, detail="Hiring staff only")

    # Verify the caller's org can see this candidate at all — reuse the
    # same gate the rest of the candidate API uses.
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise HTTPException(404, detail="Candidate not found")
    member = next(iter(current_user.memberships or []), None)
    if member is None:
        raise HTTPException(403, detail="No organisation membership found")
    # org_can_view_candidate expects the candidate UUID, not the ORM object.
    if not org_can_view_candidate(db, member.organization_id, candidate_id):
        raise HTTPException(404, detail="Candidate not found")

    try:
        content = generate_preparation(
            db,
            candidate_id=candidate_id,
            job_id=body.job_id,
            output_type=body.output_type,
            organization_id=member.organization_id,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        # Surface a clean JSON error (with CORS headers) instead of an
        # unhandled 500 that the browser reports as "Failed to fetch".
        logger.exception("preparation_generate failed for %s", body.output_type)
        raise HTTPException(
            status_code=502,
            detail=f"Preparation agent failed: {exc}",
        ) from exc

    # Persist the draft so it survives refresh and is reused until regenerated.
    # Don't clobber a previously-good draft with a failed/fallback run.
    if not (isinstance(content, dict) and content.get("agent_error")):
        try:
            save_preparation_draft(
                db,
                organization_id=member.organization_id,
                candidate_id=candidate_id,
                job_id=body.job_id,
                output_type=body.output_type,
                content=content,
                user_id=current_user.id,
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("failed to persist preparation draft")

    return PreparationGenerateOut(
        candidate_id=candidate_id,
        job_id=body.job_id,
        output_type=body.output_type,
        content=content,
    )


class PreparationListOut(BaseModel):
    candidate_id: uuid.UUID
    drafts: dict[str, Any]


@router.get(
    "/{candidate_id}/preparation",
    response_model=PreparationListOut,
)
def preparation_list(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return the saved Preparation drafts for a candidate (hiring staff only),
    so the panel shows persisted pre-analysis / question drafts on load."""
    if current_user.account_type == "candidate":
        raise HTTPException(403, detail="Hiring staff only")
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise HTTPException(404, detail="Candidate not found")
    member = next(iter(current_user.memberships or []), None)
    if member is None:
        raise HTTPException(403, detail="No organisation membership found")
    if not org_can_view_candidate(db, member.organization_id, candidate_id):
        raise HTTPException(404, detail="Candidate not found")
    drafts = get_preparation_drafts(
        db,
        organization_id=member.organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
    )
    return PreparationListOut(candidate_id=candidate_id, drafts=drafts)


# ── Candidate development & growth plan (from the hiring decision) ───────────

_DEV_STATUSES = {"todo", "in_progress", "done"}
_DEV_INFO_SECTIONS = (
    "skills_to_improve",
    "learning_resources",
    "measurable_outcomes_or_kpis",
    "manager_check_in_points",
    "evidence_to_collect",
)


def _dev_render_item(it: Any) -> str:
    if it is None:
        return ""
    if isinstance(it, (str, int, float)):
        return str(it)
    if isinstance(it, dict):
        title = (
            it.get("title") or it.get("name") or it.get("resource")
            or it.get("project_name") or ""
        )
        typ = it.get("type") or ""
        reason = it.get("reason") or it.get("description") or it.get("expected_outcome") or ""
        parts = [str(title)]
        if typ:
            parts.append("(" + str(typ) + ")")
        if reason:
            parts.append("- " + str(reason))
        s = " ".join(p for p in parts if p).strip()
        if s:
            return s
        try:
            return json.dumps(it)[:200]
        except Exception:  # noqa: BLE001
            return str(it)
    return str(it)


def _parse_month_range(key: str) -> tuple[int, int] | None:
    m = re.match(r"month_(\d+)_(\d+)", key or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _add_months(base: datetime, months: int) -> datetime:
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def _latest_dev_plan(db: Session, candidate_id: uuid.UUID) -> DevelopmentPlan | None:
    plans = db.execute(
        select(DevelopmentPlan)
        .where(DevelopmentPlan.candidate_id == candidate_id)
        .order_by(desc(DevelopmentPlan.created_at))
    ).scalars().all()
    for p in plans:
        pj = p.plan_json if isinstance(p.plan_json, dict) else {}
        if isinstance(pj.get("phases"), dict) and pj["phases"]:
            return p
    return plans[0] if plans else None


def _build_dev_plan_payload(db: Session, plan: DevelopmentPlan) -> dict[str, Any]:
    pj = plan.plan_json if isinstance(plan.plan_json, dict) else {}
    job = db.get(JobModel, plan.job_id) if plan.job_id else None
    ptype = (plan.plan_type or "").lower()
    accepted = (
        str(pj.get("decision") or "").lower() == "accepted"
        or "accept" in ptype
        or "growth" in ptype
    )

    progress = pj.get("candidate_progress") if isinstance(pj.get("candidate_progress"), dict) else {}
    items_status = progress.get("items") if isinstance(progress.get("items"), dict) else {}
    base = plan.created_at
    phases_raw = pj.get("phases") if isinstance(pj.get("phases"), dict) else {}

    def _start_month(k: str) -> int:
        r = _parse_month_range(k)
        return r[0] if r else 999

    ordered = sorted(phases_raw.keys(), key=_start_month)

    phases: list[dict[str, Any]] = []
    total = done = in_progress = todo = 0
    for k in ordered:
        ph = phases_raw[k] if isinstance(phases_raw[k], dict) else {}
        rng = _parse_month_range(k)
        start_date = end_date = None
        month_label = ""
        if rng and base is not None:
            start_date = _add_months(base, rng[0] - 1).isoformat()
            end_date = _add_months(base, rng[1]).isoformat()
            month_label = "Month " + str(rng[0]) + "-" + str(rng[1])
        raw_tasks = ph.get("tasks_or_projects") if isinstance(ph.get("tasks_or_projects"), list) else []
        tasks: list[dict[str, Any]] = []
        for i, t in enumerate(raw_tasks):
            iid = k + "::" + str(i)
            st = items_status.get(iid)
            st = st if st in _DEV_STATUSES else "todo"
            tasks.append({"id": iid, "text": _dev_render_item(t), "status": st})
            total += 1
            done += st == "done"
            in_progress += st == "in_progress"
            todo += st == "todo"
        if tasks and all(t["status"] == "done" for t in tasks):
            pstatus = "done"
        elif any(t["status"] in ("in_progress", "done") for t in tasks):
            pstatus = "in_progress"
        else:
            pstatus = "not_started"
        info = {
            sec: [_dev_render_item(x) for x in (ph.get(sec) or []) if x]
            for sec in _DEV_INFO_SECTIONS
        }
        phases.append({
            "key": k,
            "label": ph.get("label") or k.replace("_", " "),
            "month_label": month_label,
            "start_date": start_date,
            "end_date": end_date,
            "status": pstatus,
            "tasks": tasks,
            **info,
        })

    percent = round(100.0 * done / total) if total else 0
    return {
        "has_plan": True,
        "plan_id": str(plan.id),
        "job_id": str(plan.job_id) if plan.job_id else None,
        "job_title": job.title if job else None,
        "company_name": (job.company_name if job else None),
        "decision": "accepted" if accepted else "rejected",
        "plan_type": plan.plan_type,
        "title": (
            "Internal growth plan - level up & excel in this role"
            if accepted
            else "12-month plan - get the role you were rejected from"
        ),
        "duration_months": len(ordered) * 3,
        "summary": pj.get("executive_summary") or plan.summary or "",
        "candidate_message": (
            pj.get("candidate_facing_message")
            or pj.get("candidate_facing_feedback_message")
            or ""
        ),
        "started_at": base.isoformat() if base is not None else None,
        "phases": phases,
        "progress": {
            "total": total, "done": done, "in_progress": in_progress,
            "todo": todo, "percent": percent,
        },
    }


class DevPlanProgressRequest(BaseModel):
    plan_id: str
    item_id: str
    status: Literal["todo", "in_progress", "done"]


@router.get("/me/development-plan")
async def get_my_development_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The candidate's own development & growth plan, with per-phase dates and
    task progress tracking."""
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    plan = _latest_dev_plan(db, cand.id)
    if plan is None:
        return {
            "has_plan": False,
            "message": (
                "No development plan yet. Once a hiring decision is recorded for "
                "you, your personalised growth plan will appear here."
            ),
        }
    return _build_dev_plan_payload(db, plan)


@router.post("/me/development-plan/progress")
async def update_my_development_progress(
    body: DevPlanProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark one plan task as to-do / in-progress / done (candidate-owned)."""
    if current_user.account_type != "candidate":
        raise HTTPException(status_code=403, detail="Candidate account required")
    cand = current_user.candidate_profile
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    try:
        pid = uuid.UUID(body.plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid plan_id") from exc
    plan = db.get(DevelopmentPlan, pid)
    if plan is None or plan.candidate_id != cand.id:
        raise HTTPException(status_code=404, detail="Development plan not found")

    pj = dict(plan.plan_json) if isinstance(plan.plan_json, dict) else {}
    progress = dict(pj.get("candidate_progress") or {})
    items = dict(progress.get("items") or {})
    if body.status == "todo":
        items.pop(body.item_id, None)
    else:
        items[body.item_id] = body.status
    progress["items"] = items
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    pj["candidate_progress"] = progress
    plan.plan_json = pj  # reassign so SQLAlchemy flags the JSONB column dirty
    db.commit()
    db.refresh(plan)
    return _build_dev_plan_payload(db, plan)


# ── Candidate application roadmap: interview details + anonymized ranking ────


def _dedupe(seq: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in seq:
        s = (str(s) if s is not None else "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) >= limit:
            break
    return out


# Pipeline stage kind → Interview.interview_type used to disambiguate when a
# job configures several interview rounds (HR / technical / mixed).
_STAGE_KIND_TO_INTERVIEW_TYPE: dict[str, str] = {
    "hr_interview": "hr",
    "technical_interview": "technical",
    "mixed_interview": "mixed",
}


@router.get("/me/applications/{app_id}/interview")
async def get_my_application_interview(
    app_id: uuid.UUID,
    kind: str | None = Query(None, description="Pipeline stage kind to filter by"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The candidate's interview details for one application — summary, key
    points and strengths (candidate-safe; no raw rejection scoring).

    When ``kind`` is supplied (e.g. ``technical_interview``) the lookup is
    narrowed to that interview round so multi-round pipelines stay distinct.
    """
    cand, app = _require_candidate_app(db, current_user, app_id)
    want_type = _STAGE_KIND_TO_INTERVIEW_TYPE.get((kind or "").strip().lower())

    def _query(*extra):
        stmt = (
            select(Interview)
            .where(Interview.candidate_id == cand.id, *extra)
            .order_by(desc(Interview.updated_at), desc(Interview.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalars().first()

    type_filter = (Interview.interview_type == want_type,) if want_type else ()
    inv = _query(Interview.application_id == app.id, *type_filter)
    if inv is None and app.job_id:
        inv = _query(Interview.job_id == app.job_id, *type_filter)
    # If a specific round was requested but not found, fall back to any round
    # so the candidate still sees something useful rather than an empty panel.
    if inv is None and want_type:
        inv = _query(Interview.application_id == app.id) or (
            _query(Interview.job_id == app.job_id) if app.job_id else None
        )
    if inv is None:
        return {
            "has_interview": False,
            "message": "This interview round hasn't been scheduled yet.",
        }

    summ = db.execute(
        select(InterviewSummary)
        .where(InterviewSummary.interview_id == inv.id)
        .order_by(desc(InterviewSummary.created_at))
        .limit(1)
    ).scalars().first()
    sj = summ.summary_json if (summ and isinstance(summ.summary_json, dict)) else {}

    evals = db.execute(
        select(InterviewEvaluation).where(InterviewEvaluation.interview_id == inv.id)
    ).scalars().all()

    strengths: list[str] = [str(x) for x in (sj.get("strengths_observed") or [])]
    for e in evals:
        esj = e.score_json if isinstance(e.score_json, dict) else {}
        strengths += [str(x) for x in (esj.get("strengths") or [])]
        if isinstance(e.strengths_json, list):
            strengths += [str(x) for x in e.strengths_json]

    key_points: list[str] = []
    ka = sj.get("key_answers")
    if isinstance(ka, dict):
        for k, v in ka.items():
            if v:
                key_points.append(f"{str(k).replace('_', ' ').title()}: {v}")
    elif isinstance(ka, list):
        key_points = [str(x) for x in ka]
    if not key_points:
        key_points = [str(x) for x in (sj.get("important_quotes_or_answer_evidence") or [])]

    summary_text = (
        sj.get("short_summary")
        or sj.get("detailed_summary")
        or ""
    )
    return {
        "has_interview": True,
        "interview_type": inv.interview_type,
        "status": inv.status,
        "scheduled_at": inv.scheduled_start_time.isoformat() if inv.scheduled_start_time else None,
        "summary": summary_text,
        "key_points": _dedupe(key_points, 8),
        "strengths": _dedupe(strengths, 8),
        "analysed": bool(summ is not None or evals),
    }


@router.get("/me/applications/{app_id}/ranking")
async def get_my_application_ranking(
    app_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Anonymized ranking of all candidates scored for this job — each with a
    score, strengths and a why. The current candidate is highlighted as 'You'."""
    cand, app = _require_candidate_app(db, current_user, app_id)
    if not app.job_id:
        return {"has_ranking": False, "message": "No ranking available yet."}

    runs = db.execute(
        select(ScreeningRun)
        .where(ScreeningRun.job_id == app.job_id)
        .order_by(desc(ScreeningRun.created_at))
    ).scalars().all()
    run = None
    for r in runs:
        cnt = db.execute(
            select(func.count())
            .select_from(ScreeningResult)
            .where(ScreeningResult.screening_run_id == r.id)
        ).scalar()
        if cnt:
            run = r
            break
    if run is None:
        return {
            "has_ranking": False,
            "message": (
                "Your ranking will appear once the hiring team has scored the "
                "candidates for this role."
            ),
        }

    rows = db.execute(
        select(ScreeningResult)
        .where(ScreeningResult.screening_run_id == run.id)
        .order_by(
            ScreeningResult.rank_position.asc().nullslast(),
            ScreeningResult.final_score.desc(),
        )
    ).scalars().all()

    job = db.get(JobModel, app.job_id)
    results: list[dict[str, Any]] = []
    your_rank: int | None = None
    you_in = False
    for i, r in enumerate(rows, start=1):
        is_you = r.candidate_id == cand.id
        rank = r.rank_position or i
        if is_you:
            you_in = True
            your_rank = rank
        results.append({
            "rank": rank,
            "label": "You" if is_you else (r.blind_label or f"Candidate {i}"),
            "is_you": is_you,
            "score": round(float(r.final_score or 0), 1),
            "strengths": [str(x) for x in (r.strengths or []) if x][:5],
            "explanation": (r.explanation or "")[:600],
            "recommendation": r.recommendation,
        })

    return {
        "has_ranking": True,
        "job_title": job.title if job else None,
        "total": len(results),
        "your_rank": your_rank,
        "you_in_ranking": you_in,
        "results": results[:25],
    }
