"""Candidate-side Job Description Analysis service (fix8&9 Update 1).

Single entry point: :pyfunc:`analyze_job_description_for_candidate`.

The agent receives the candidate's own profile, CV summary, skills,
experience, projects, and education along with the job description text
and returns a JSON object the UI renders directly.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate
from app.db.models.cv_entities import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateSkill,
)
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

logger = logging.getLogger(__name__)


_SCHEMA = """{
  "overall_fit_score": <int 0..100>,
  "summary": "<2-4 sentences, candidate-facing>",
  "matching_skills": ["<skill present in both>", ...],
  "missing_skills": ["<skill required but absent>", ...],
  "weak_skills": ["<skill present but unclear evidence>", ...],
  "experience_alignment": "<short paragraph>",
  "project_alignment": "<short paragraph>",
  "education_alignment": "<short paragraph>",
  "recommended_improvements": ["<a specific, achievable step that moves the candidate from their CURRENT profile toward THIS job's requirements — name the gap it closes and build on what they already have>", ...],
  "interview_preparation": ["<bullet>", ...],
  "learning_recommendations": ["<bullet>", ...]
}"""


_SYSTEM_PROMPT = (
    "You are the PATHS Candidate Job-Description Coach.\n\n"
    "Your job is to help an individual candidate decide whether a job is "
    "a good fit for THEM and what they should do to prepare.\n\n"
    "Rules:\n"
    "  • Use ONLY the candidate evidence provided — never invent skills, "
    "employers, or experience the candidate did not list.\n"
    "  • Use ONLY the job description provided — never invent requirements.\n"
    "  • Be supportive but honest about gaps. Frame gaps as actionable "
    "improvements, not personal flaws.\n"
    "  • 'recommended_improvements' MUST be a personalised, prioritised "
    "action plan: start from the candidate's CURRENT skills/experience and "
    "give concrete, achievable steps to meet THIS job's requirements. Each "
    "step names the gap it closes and, where possible, builds on something "
    "the candidate already has. Order highest-impact first; no generic "
    "advice that ignores their actual profile.\n"
    "  • Do NOT mention or infer protected attributes (gender, age, race, "
    "religion, marital status, disability, nationality, political views).\n"
    "  • Address the candidate in second person ('you', 'your profile').\n"
    "  • Output ONLY a single JSON object matching the requested schema; "
    "no Markdown, no preamble, no trailing prose."
)


# ── Candidate context builder ───────────────────────────────────────────────


def _build_candidate_context(db: Session, candidate_id: UUID) -> dict[str, Any]:
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")

    # Skills via normalized table when present; fall back to free-text array.
    skills_named: list[str] = []
    cs_rows = db.execute(
        select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)
    ).scalars().all()
    for cs in cs_rows:
        sk_rel = getattr(cs, "skill", None)
        name = getattr(sk_rel, "normalized_name", None) if sk_rel else None
        if isinstance(name, str) and name.strip():
            skills_named.append(name.strip())
    if not skills_named and isinstance(cand.skills, list):
        skills_named = [str(s) for s in cand.skills if str(s).strip()]

    experiences = []
    for e in db.execute(
        select(CandidateExperience)
        .where(CandidateExperience.candidate_id == candidate_id)
        .order_by(CandidateExperience.start_date.desc().nullslast())
    ).scalars().all()[:8]:
        experiences.append({
            "title": (e.title or "").strip(),
            "duration": f"{e.start_date or ''} → {e.end_date or 'present'}".strip(),
            "description": (e.description or "").strip()[:1200],
        })

    educations = []
    for ed in db.execute(
        select(CandidateEducation).where(CandidateEducation.candidate_id == candidate_id)
    ).scalars().all()[:5]:
        educations.append({
            "degree": (ed.degree or "").strip(),
            "field": (ed.field_of_study or "").strip(),
        })

    certifications = []
    for c in db.execute(
        select(CandidateCertification).where(CandidateCertification.candidate_id == candidate_id)
    ).scalars().all()[:10]:
        if c.name:
            certifications.append(c.name)

    summary = (cand.summary or "").strip()[:1500]
    headline = (cand.headline or "").strip()[:300]

    return {
        "current_title":     (cand.current_title or "").strip() or None,
        "years_experience":  cand.years_experience,
        "career_level":      cand.career_level,
        "headline":          headline or None,
        "summary":           summary or None,
        "skills":            skills_named,
        "experience":        experiences,
        "education":         educations,
        "certifications":    certifications,
    }


# ── Lightweight skill heuristics for the fallback path ─────────────────────


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,30}")
_STOP = frozenset({
    "a", "an", "and", "the", "with", "for", "of", "in", "on", "at", "by",
    "or", "to", "from", "as", "is", "are", "be", "was", "were", "we",
    "must", "should", "have", "has", "had", "experience", "years", "year",
    "engineer", "developer", "role", "team", "company", "you", "your",
})


def _keywords(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _TOKEN_RE.finditer(text or ""):
        t = m.group(0)
        n = t.lower()
        if n in _STOP or n in seen:
            continue
        seen.add(n)
        out.append(t)
    return out


def _deterministic_fallback(
    candidate: dict[str, Any], job_description: str, reason: str,
) -> dict[str, Any]:
    """Last-ditch result when OpenRouter is unavailable.

    Builds a usable analysis from keyword overlap so the candidate page
    never crashes. The agent error is surfaced in ``summary``.
    """
    jd_kw = _keywords(job_description)
    cand_corpus_parts = [
        " ".join(candidate.get("skills") or []),
        " ".join(e.get("title", "") for e in candidate.get("experience", [])),
        " ".join(e.get("description", "") for e in candidate.get("experience", [])),
        candidate.get("summary") or "",
        candidate.get("headline") or "",
    ]
    cand_corpus = " ".join(p for p in cand_corpus_parts if p).lower()

    matching: list[str] = []
    missing: list[str] = []
    for kw in jd_kw[:40]:
        if kw.lower() in cand_corpus:
            matching.append(kw)
        else:
            missing.append(kw)

    overall = int(round(100 * len(matching) / max(1, len(jd_kw)))) if jd_kw else 50

    return {
        "overall_fit_score": overall,
        "summary": (
            "Automated analysis fell back to keyword overlap because the AI "
            f"coach is currently unavailable ({reason[:80]}). Your profile "
            f"matches roughly {overall}% of the keyword signals in this job."
        ),
        "matching_skills": matching[:15],
        "missing_skills": missing[:15],
        "weak_skills": [],
        "experience_alignment": "Detailed alignment unavailable — agent offline.",
        "project_alignment": "Detailed alignment unavailable — agent offline.",
        "education_alignment": "Detailed alignment unavailable — agent offline.",
        "recommended_improvements": [
            "Retry the analysis in a few minutes for a full personalised response.",
        ],
        "interview_preparation": [],
        "learning_recommendations": [
            f"Brush up on: {', '.join(missing[:5])}" if missing else
            "No clear gaps detected from keyword overlap — full coach offline.",
        ],
        "used_fallback": True,
        "fallback_reason": reason[:200],
    }


# ── Public entry ────────────────────────────────────────────────────────────


def analyze_job_description_for_candidate(
    db: Session,
    *,
    candidate_id: UUID,
    job_description_text: str,
) -> dict[str, Any]:
    """Analyse a JD against the candidate's profile and return a structured dict."""
    jd = (job_description_text or "").strip()
    if len(jd) < 30:
        raise ValueError("job_description_too_short")

    context = _build_candidate_context(db, candidate_id)

    user_prompt = (
        "Compare this job description against the candidate's profile and "
        "produce a candidate-facing analysis.\n\n"
        f"Candidate profile (JSON):\n{context}\n\n"
        f"Job description:\n{jd[:8000]}\n\n"
        "For 'recommended_improvements', write a PERSONALISED, PRIORITISED "
        "action plan tailored to THIS candidate's current state: for each "
        "important requirement in the job that the candidate does not yet "
        "clearly meet (see missing_skills / weak_skills), give ONE specific, "
        "achievable step. Each step should say what to do and how, and — when "
        "relevant — build on a skill or experience they ALREADY have (name it, "
        "e.g. 'You already use X; extend it by …'). Avoid generic advice that "
        "would apply to anyone. Order from highest-impact to lowest.\n\n"
        "Return ONLY a JSON object matching this schema:\n"
        f"{_SCHEMA}\n"
    )

    try:
        raw = generate_json_response(
            _SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=2600,
        )
    except OpenRouterClientError as exc:
        return _deterministic_fallback(context, jd, reason=str(exc)[:200])
    except Exception as exc:  # noqa: BLE001
        logger.exception("[jd_analysis] agent crashed: %s", exc)
        return _deterministic_fallback(context, jd, reason=f"{type(exc).__name__}: {exc}")

    if not isinstance(raw, dict):
        return _deterministic_fallback(context, jd, reason="non-object output")

    # Normalize the response so the UI always has well-typed fields.
    def _strlist(v: Any, cap: int = 20) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()][:cap]
        if isinstance(v, str) and v.strip():
            return [v.strip()][:cap]
        return []

    try:
        overall = int(raw.get("overall_fit_score") or 0)
    except (TypeError, ValueError):
        overall = 0
    overall = max(0, min(100, overall))

    missing = _strlist(raw.get("missing_skills"))
    weak = _strlist(raw.get("weak_skills"))
    improvements = _strlist(raw.get("recommended_improvements"))

    # Safety net: the candidate must always get an action plan. If the model
    # omitted recommended_improvements, synthesise concrete steps from the
    # detected gaps (missing/weak skills) so the tips stay grounded in the
    # candidate's real profile-vs-JD difference rather than disappearing.
    if not improvements:
        improvements = [
            f"Close your gap on {skill}: build a small project or take a focused "
            f"course, then add the result to your CV so it's visible to recruiters."
            for skill in (missing or weak)[:5]
        ]

    return {
        "overall_fit_score": overall,
        "summary": str(raw.get("summary") or "").strip(),
        "matching_skills": _strlist(raw.get("matching_skills")),
        "missing_skills": missing,
        "weak_skills": weak,
        "experience_alignment": str(raw.get("experience_alignment") or "").strip(),
        "project_alignment": str(raw.get("project_alignment") or "").strip(),
        "education_alignment": str(raw.get("education_alignment") or "").strip(),
        "recommended_improvements": improvements,
        "interview_preparation": _strlist(raw.get("interview_preparation")),
        "learning_recommendations": _strlist(raw.get("learning_recommendations")),
        "used_fallback": False,
    }
