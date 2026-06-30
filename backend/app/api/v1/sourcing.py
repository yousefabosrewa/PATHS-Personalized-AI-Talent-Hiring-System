"""
PATHS Backend — Sourcing page (two-tab) helper endpoints.

Adds the minimum two routes the redesigned sourcing page needs:

  GET  /api/v1/sourcing/database-candidates
       Real candidates already in the platform (signed up / imported / synced).
       Distinct from `/api/v1/organization-candidate-sourcing/candidates`,
       which serves the LinkedIn Open-to-Work pool.

  POST /api/v1/sourcing/candidates/{candidate_id}/explain
       Generic, provider-flexible candidate explanation. Tries the configured
       agent first; falls back to a rule-based summary so the UI never breaks.

Both routes are gated behind ``require_active_org_status`` — they only read
candidates the caller's organisation can already see (sourced candidates the
org owns + the platform's open candidate pool with a profile).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    require_active_org_status,
)
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateExperience
from app.db.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sourcing", tags=["Sourcing"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class DatabaseCandidateOut(BaseModel):
    candidate_id: str
    full_name: str
    current_title: str | None = None
    location_text: str | None = None
    headline: str | None = None
    summary: str | None = None
    years_experience: int | None = None
    skills: list[str] = Field(default_factory=list)
    source_type: str | None = None
    status: str | None = None


class DatabaseCandidateListOut(BaseModel):
    total: int
    items: list[DatabaseCandidateOut]


class ExplainRequest(BaseModel):
    job_id: str | None = None
    source: Literal["database", "system_candidate", "linkedin_open_to_work"] | None = None


class ExplainResponse(BaseModel):
    candidate_id: str
    summary: str
    fit_explanation: str
    strengths: list[str]
    gaps: list[str]
    risks: list[str]
    recommended_action: Literal[
        "Shortlist", "Review manually", "Request more information", "Reject for now"
    ]
    confidence: float
    used_fallback: bool


# ── Helpers ──────────────────────────────────────────────────────────────────


_INTERNAL_SOURCE_TYPES = {
    # Candidate.source_type values that mean "already on the platform".
    "paths_profile",     # signed-up candidate user
    "imported",          # bulk-imported via CSV / admin
    "uploaded",          # CV upload that created a candidate
    "manual",            # manually entered by recruiter
    None,                # legacy rows with no source_type set
    "",
}


def _serialize_candidate(cand: Candidate) -> DatabaseCandidateOut:
    return DatabaseCandidateOut(
        candidate_id=str(cand.id),
        full_name=cand.full_name or "—",
        current_title=cand.current_title,
        location_text=cand.location_text,
        headline=cand.headline,
        summary=cand.summary,
        years_experience=cand.years_experience,
        skills=list(cand.skills or [])[:30],
        source_type=cand.source_type,
        status=cand.status,
    )


def _fallback_explanation(
    cand: Candidate, job: Job | None, recent_exp_titles: list[str], reason: str,
) -> ExplainResponse:
    """A deterministic, rule-based explanation used when the LLM is unavailable.

    Never raises — works from whatever profile data the candidate already has.
    """
    skills = list(cand.skills or [])
    has_signal = bool(cand.summary or skills or recent_exp_titles or cand.current_title)
    if not has_signal:
        return ExplainResponse(
            candidate_id=str(cand.id),
            summary="Not enough evidence available.",
            fit_explanation=(
                "The candidate profile does not contain enough skills, "
                "experience, or job-matching evidence to generate a reliable "
                "explanation."
            ),
            strengths=[],
            gaps=["Insufficient candidate data"],
            risks=["Low evidence confidence"],
            recommended_action="Review manually",
            confidence=0.2,
            used_fallback=True,
        )

    strengths: list[str] = []
    if cand.current_title:
        strengths.append(f"Current role: {cand.current_title}")
    if cand.years_experience:
        strengths.append(f"{cand.years_experience} years of experience")
    if skills:
        strengths.append(f"Skills on file: {', '.join(skills[:6])}")
    if recent_exp_titles:
        strengths.append(f"Recent roles: {', '.join(recent_exp_titles[:3])}")

    gaps: list[str] = []
    risks: list[str] = []
    if not skills:
        gaps.append("No skills listed on profile yet.")
        risks.append("Hard to match without a skill list.")
    if job is not None:
        required = [s for s in (job.requirements or "").split(",") if s.strip()]
        missing = [s for s in required if s.strip().lower() not in {sk.lower() for sk in skills}]
        if missing:
            gaps.append(f"Missing vs job requirements: {', '.join(missing[:5])}")

    confidence = 0.45 if skills else 0.25
    return ExplainResponse(
        candidate_id=str(cand.id),
        summary=(
            f"{cand.full_name or 'Candidate'} — "
            f"{cand.current_title or 'role unspecified'}"
            + (f", {cand.location_text}" if cand.location_text else "")
            + (f". {cand.summary[:240]}" if cand.summary else "")
        ),
        fit_explanation=(
            "The AI explanation service is currently unavailable, so this "
            "summary was generated from available profile fields. "
            f"({reason})"
        ),
        strengths=strengths or ["Some profile data on file"],
        gaps=gaps or ["No specific gaps detected from available data"],
        risks=risks,
        recommended_action="Review manually",
        confidence=confidence,
        used_fallback=True,
    )


def _build_agent_prompt(cand: Candidate, job: Job | None, recent_exp_titles: list[str]) -> tuple[str, str]:
    system = (
        "You are a recruitment decision-support agent. "
        "Generate a concise, evidence-based explanation for the candidate. "
        "Use only the provided candidate data, profile data, CV summary, "
        "skills, experience, and optional job requirements. "
        "Do not invent missing information. "
        'If evidence is missing, clearly say: "Not enough evidence available." '
        "Return STRICT JSON only — no markdown — with the keys: "
        "summary, fit_explanation, strengths (array), gaps (array), "
        "risks (array), recommended_action "
        '(one of "Shortlist", "Review manually", "Request more information", "Reject for now"), '
        "confidence (0..1)."
    )
    lines = [
        f"Candidate name: {cand.full_name or '(unknown)'}",
        f"Current title: {cand.current_title or '(unspecified)'}",
        f"Location: {cand.location_text or '(unspecified)'}",
        f"Years of experience: {cand.years_experience or '(unspecified)'}",
        f"Skills on file: {', '.join((cand.skills or [])[:30]) or '(none)'}",
        f"Recent experience titles: {', '.join(recent_exp_titles[:5]) or '(none)'}",
        f"Profile summary: {cand.summary or '(none)'}",
    ]
    if job is not None:
        lines += [
            "",
            f"Target job title: {job.title or '(unspecified)'}",
            f"Job description: {(job.description_text or '(none)')[:1200]}",
            f"Job requirements: {(job.requirements or '(none)')[:800]}",
        ]
    user = "\n".join(lines) + "\n\nProduce the structured JSON explanation now."
    return system, user


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/jobs/{job_id}/shortlisted", response_model=list[str])
def list_shortlisted_for_job(
    job_id: uuid.UUID,
    ctx: OrgContext = Depends(require_active_org_status),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> list[str]:
    """Candidate ids currently on this job's shortlist.

    Lets the sourcing page re-paint the "Shortlisted" badge after a hard
    refresh — the page seeds its local set from this response on mount.
    Reads the existing ``applications`` table (same one the shortlist POST
    writes to), no new schema.
    """
    rows = db.execute(
        select(Application.candidate_id)
        .where(
            Application.job_id == job_id,
            Application.current_stage_code.in_(("sourced", "shortlisted")),
        )
    ).all()
    return [str(r[0]) for r in rows]


@router.get("/database-candidates", response_model=DatabaseCandidateListOut)
def list_database_candidates(
    ctx: OrgContext = Depends(require_active_org_status),  # noqa: ARG001
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Free-text filter (name / title / location)"),
    limit: int = Query(default=50, ge=1, le=200),
) -> DatabaseCandidateListOut:
    """Real candidates already in the platform (signed up + imported + manual)."""
    stmt = (
        select(Candidate)
        .where(
            or_(
                Candidate.source_type.is_(None),
                Candidate.source_type.in_(list(s for s in _INTERNAL_SOURCE_TYPES if s)),
            ),
            (Candidate.status == "active") | Candidate.status.is_(None),
        )
        .order_by(Candidate.created_at.desc())
        .limit(limit)
    )
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Candidate.full_name.ilike(needle),
                Candidate.current_title.ilike(needle),
                Candidate.location_text.ilike(needle),
                Candidate.headline.ilike(needle),
            )
        )
    rows = db.execute(stmt).scalars().all()
    items = [_serialize_candidate(c) for c in rows]
    return DatabaseCandidateListOut(total=len(items), items=items)


@router.post(
    "/candidates/{candidate_id}/explain",
    response_model=ExplainResponse,
    status_code=status.HTTP_200_OK,
)
def explain_candidate(
    candidate_id: str,
    body: ExplainRequest,
    ctx: OrgContext = Depends(require_active_org_status),  # noqa: ARG001
    db: Session = Depends(get_db),
) -> ExplainResponse:
    """Provider-flexible candidate explanation.

    Tries the configured agent (OpenRouter via ``generate_json_response`` —
    which itself walks a chain of free models). On any failure or invalid
    JSON, returns a rule-based fallback. The UI never breaks.
    """
    try:
        cand_uuid = uuid.UUID(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid candidate_id") from exc

    cand = db.get(Candidate, cand_uuid)
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job: Job | None = None
    if body.job_id:
        try:
            job = db.get(Job, uuid.UUID(body.job_id))
        except ValueError:
            job = None  # Bad job id — quietly explain without job context.

    # Recent experience titles for prompt context.
    recent_exp = db.execute(
        select(CandidateExperience.title)
        .where(CandidateExperience.candidate_id == cand.id)
        .order_by(CandidateExperience.created_at.desc())
        .limit(5)
    ).scalars().all()
    recent_exp_titles = [t for t in recent_exp if t]

    # ── Try the agent ─────────────────────────────────────────────────────
    try:
        # Local import keeps the module importable even if the LLM client
        # has a startup hiccup — we still serve the fallback below.
        from app.services.llm.openrouter_client import (
            OpenRouterClientError,
            generate_json_response,
        )
    except Exception as exc:  # pragma: no cover - safety net
        return _fallback_explanation(cand, job, recent_exp_titles, f"client import failed: {exc}")

    system_prompt, user_prompt = _build_agent_prompt(cand, job, recent_exp_titles)
    try:
        raw: dict[str, Any] = generate_json_response(
            system_prompt, user_prompt, temperature=0.1, max_tokens=900,
        )
    except OpenRouterClientError as exc:
        return _fallback_explanation(cand, job, recent_exp_titles, str(exc)[:120])
    except Exception as exc:  # noqa: BLE001
        logger.warning("explain_candidate: agent failed (%s) — falling back", exc)
        return _fallback_explanation(cand, job, recent_exp_titles, "agent error")

    # Coerce + validate the agent's JSON shape — defensive, never crashes.
    def _strlist(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if x is not None and str(x).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    action_raw = str(raw.get("recommended_action") or "").strip()
    allowed_actions = {
        "Shortlist", "Review manually", "Request more information", "Reject for now",
    }
    if action_raw not in allowed_actions:
        # Best-effort normalisation; otherwise default safely.
        canon = {a.lower(): a for a in allowed_actions}
        action_raw = canon.get(action_raw.lower(), "Review manually")

    try:
        confidence = float(raw.get("confidence") or 0.5)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    summary = str(raw.get("summary") or "").strip()
    fit = str(raw.get("fit_explanation") or "").strip()
    if not summary and not fit:
        # Agent returned an empty shell — use the fallback for substance.
        return _fallback_explanation(cand, job, recent_exp_titles, "empty agent output")

    return ExplainResponse(
        candidate_id=str(cand.id),
        summary=summary or "Not enough evidence available.",
        fit_explanation=fit or summary,
        strengths=_strlist(raw.get("strengths")),
        gaps=_strlist(raw.get("gaps")),
        risks=_strlist(raw.get("risks")),
        recommended_action=action_raw,  # type: ignore[arg-type]
        confidence=confidence,
        used_fallback=False,
    )
