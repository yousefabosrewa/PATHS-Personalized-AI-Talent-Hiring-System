"""
PATHS Backend — Candidate↔Job reasoning agent.

Asks the local Llama (via OpenRouter or Ollama, mirroring the existing
scoring agent settings) to produce a short, JSON-structured explanation
of why a sourced candidate matches — or does not match — a given job.

Falls back to a deterministic, template-based explanation when:
  * the OpenRouter key is missing, or
  * `CANDIDATE_SOURCING_REASONING_ENABLED=false`, or
  * the model call fails for any reason.

The deterministic fallback is intentionally simple so the UI always has
*something* to render, even in air-gapped / offline development setups.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import candidates_relational, jobs_relational
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CandidateJobReasoning:
    candidate_id: str
    job_id: str
    decision: str             # "strong_match" | "potential_match" | "weak_match"
    overall_score: float      # 0..100 (echoed from the matcher)
    summary: str              # short one-paragraph explanation (LLM or fallback)
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    recommended_next_step: str = "review_profile"
    model: str | None = None
    fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def explain_candidate_job_match(
    db: Session,
    *,
    candidate_id: UUID,
    job_id: UUID,
    overall_score: float,
    matched_skills: list[str] | None = None,
    missing_required_skills: list[str] | None = None,
) -> CandidateJobReasoning:
    """Return a structured reasoning object for the Match panel UI."""

    matched = list(matched_skills or [])
    missing = list(missing_required_skills or [])
    job_profile = jobs_relational.get_job_full_profile(db, job_id)
    cand_profile = candidates_relational.get_candidate_full_profile(db, candidate_id)
    if job_profile is None or cand_profile is None:
        return _fallback_reasoning(
            candidate_id=candidate_id,
            job_id=job_id,
            overall_score=overall_score,
            matched_skills=matched,
            missing_required_skills=missing,
            note="missing profile",
        )

    if not settings.candidate_sourcing_reasoning_enabled:
        return _fallback_reasoning(
            candidate_id=candidate_id,
            job_id=job_id,
            overall_score=overall_score,
            matched_skills=matched,
            missing_required_skills=missing,
        )

    if not settings.openrouter_api_key:
        # Local-only mode — produce the deterministic explanation.
        return _fallback_reasoning(
            candidate_id=candidate_id,
            job_id=job_id,
            overall_score=overall_score,
            matched_skills=matched,
            missing_required_skills=missing,
            note="openrouter key missing",
        )

    try:
        prompt_user = _build_user_prompt(
            cand_profile=cand_profile,
            job_profile=job_profile,
            overall_score=overall_score,
            matched_skills=matched,
            missing_required_skills=missing,
        )
        data = generate_json_response(
            _SYSTEM_PROMPT,
            prompt_user,
            model=settings.candidate_sourcing_reasoning_model,
            temperature=float(settings.candidate_sourcing_reasoning_temperature),
            max_tokens=int(settings.candidate_sourcing_reasoning_max_tokens),
        )
    except OpenRouterClientError as exc:
        logger.warning("[CandidateSourcing] reasoning model failed: %s", exc)
        return _fallback_reasoning(
            candidate_id=candidate_id,
            job_id=job_id,
            overall_score=overall_score,
            matched_skills=matched,
            missing_required_skills=missing,
            note=f"llm_error:{exc}",
        )

    decision = _coerce_decision(data.get("decision"), overall_score)
    return CandidateJobReasoning(
        candidate_id=str(candidate_id),
        job_id=str(job_id),
        decision=decision,
        overall_score=float(overall_score),
        summary=str(data.get("summary") or "").strip()[:1500] or _summary_template(decision, overall_score),
        strengths=_safe_str_list(data.get("strengths"), max_items=6),
        gaps=_safe_str_list(data.get("gaps"), max_items=6) or list(missing[:3]),
        red_flags=_safe_str_list(data.get("red_flags"), max_items=4),
        recommended_next_step=str(
            data.get("recommended_next_step") or "review_profile"
        ).strip()[:200],
        model=settings.candidate_sourcing_reasoning_model,
        fallback=False,
    )


# ── Prompt construction ──────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are PATHS, a recruitment reasoning assistant. You read a structured "
    "candidate profile and a job description and you decide how well the "
    "candidate matches the job. You MUST reply with a single valid JSON object "
    "matching this schema and nothing else:\n"
    "{\n"
    '  "decision": "strong_match" | "potential_match" | "weak_match",\n'
    '  "summary": "1-3 sentence plain-English explanation",\n'
    '  "strengths": ["short bullet", ...],\n'
    '  "gaps": ["short bullet", ...],\n'
    '  "red_flags": ["short bullet", ...],\n'
    '  "recommended_next_step": "review_profile" | "shortlist" | "outreach" | "skip"\n'
    "}\n"
    "Be specific about skills, seniority, location, and remote preference. "
    "Never invent contact details. Never reveal raw notes."
)


def _build_user_prompt(
    *,
    cand_profile,
    job_profile,
    overall_score: float,
    matched_skills: list[str],
    missing_required_skills: list[str],
) -> str:
    c = cand_profile.candidate
    j = job_profile.job
    skills = ", ".join(
        sorted({(sk.normalized_name or "").lower() for _, sk in cand_profile.skills if sk})
    ) or "-"
    direct_skills = ", ".join(c.skills or []) or "-"
    desired = ", ".join(c.desired_job_titles or []) or "-"
    workplace = ", ".join(c.open_to_workplace_settings or []) or "-"
    employment = ", ".join(c.open_to_job_types or []) or "-"

    job_skills = ", ".join(
        sorted({jsr.skill_name_normalized for jsr, _ in job_profile.skill_requirements if jsr.skill_name_normalized})
    ) or "-"

    return (
        f"Job:\n"
        f"- title: {j.title}\n"
        f"- company: {j.company_name or '-'}\n"
        f"- location: {j.location_text or '-'} ({j.location_mode or j.workplace_type or '-'})\n"
        f"- seniority: {j.seniority_level or '-'}\n"
        f"- employment_type: {j.employment_type}\n"
        f"- min/max years: {j.min_years_experience}/{j.max_years_experience}\n"
        f"- required & preferred skills: {job_skills}\n"
        f"- summary: {(j.summary or j.description_text or '').strip()[:1200]}\n\n"
        f"Candidate:\n"
        f"- full_name: {c.full_name}\n"
        f"- current_title: {c.current_title or '-'}\n"
        f"- location: {c.location_text or '-'}\n"
        f"- years_experience: {c.years_experience or '-'}\n"
        f"- desired_titles: {desired}\n"
        f"- open_to_workplace: {workplace}\n"
        f"- open_to_job_types: {employment}\n"
        f"- structured_skills: {skills}\n"
        f"- direct_skills: {direct_skills}\n"
        f"- summary: {(c.summary or '').strip()[:800]}\n\n"
        f"Pre-computed signals:\n"
        f"- overall_score (0..100): {overall_score:.1f}\n"
        f"- matched_skills: {', '.join(matched_skills) or '-'}\n"
        f"- missing_required_skills: {', '.join(missing_required_skills) or '-'}\n\n"
        "Return JSON only."
    )


# ── Fallback / helpers ───────────────────────────────────────────────────


def _fallback_reasoning(
    *,
    candidate_id: UUID,
    job_id: UUID,
    overall_score: float,
    matched_skills: list[str],
    missing_required_skills: list[str],
    note: str | None = None,
) -> CandidateJobReasoning:
    decision = _coerce_decision(None, overall_score)
    summary = _summary_template(decision, overall_score)
    if note:
        summary = f"{summary} (offline reasoning — {note})"
    return CandidateJobReasoning(
        candidate_id=str(candidate_id),
        job_id=str(job_id),
        decision=decision,
        overall_score=float(overall_score),
        summary=summary,
        strengths=[f"Matches skill: {s}" for s in matched_skills[:5]],
        gaps=[f"Missing required: {s}" for s in missing_required_skills[:5]],
        red_flags=[],
        recommended_next_step=_recommend_next(decision),
        model=None,
        fallback=True,
    )


def _summary_template(decision: str, score: float) -> str:
    if decision == "strong_match":
        return (
            f"Strong overall fit (score {score:.0f}/100). The candidate "
            "covers most required skills and meets the role's seniority signals."
        )
    if decision == "potential_match":
        return (
            f"Possible fit (score {score:.0f}/100). The candidate has partial "
            "skill coverage; review CV and ask targeted questions on the gaps."
        )
    return (
        f"Weak fit (score {score:.0f}/100). The candidate may be open to work "
        "but the skill / seniority alignment with this job is limited."
    )


def _recommend_next(decision: str) -> str:
    if decision == "strong_match":
        return "shortlist"
    if decision == "potential_match":
        return "review_profile"
    return "skip"


def _coerce_decision(value: Any, overall_score: float) -> str:
    canonical = {"strong_match", "potential_match", "weak_match"}
    if isinstance(value, str) and value.strip().lower() in canonical:
        return value.strip().lower()
    if overall_score >= 75:
        return "strong_match"
    if overall_score >= 50:
        return "potential_match"
    return "weak_match"


def _safe_str_list(value: Any, *, max_items: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for v in value:
        if isinstance(v, str):
            s = v.strip()
            if s:
                out.append(s[:200])
        if len(out) >= max_items:
            break
    return out


def serialize(reasoning: CandidateJobReasoning) -> dict[str, Any]:
    """Convenience wrapper for the API layer."""
    try:
        return reasoning.to_dict()
    except TypeError:
        return json.loads(json.dumps(asdict(reasoning), default=str))
