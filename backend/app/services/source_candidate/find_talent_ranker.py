"""
PATHS Backend — Find Talent ranking agent.

Ranks a pool of just-sourced candidates (LinkedIn outbound + optionally the
org's database) against a target job (or, when no job is chosen, against the
free-text search query). The agent scores each candidate 0–100 and writes a
short "why this match" explanation; results are returned highest-score-first.

LLM: OpenRouter (``generate_json_response``) — one batched call ranks the
whole pool. A deterministic keyword/skill-overlap fallback runs when the LLM
is unavailable or errors, so the panel always returns a sensible ranking.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import jobs_relational
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

logger = logging.getLogger(__name__)
settings = get_settings()

_WORD_RE = re.compile(r"[a-z0-9+#.]+")


@dataclass
class TalentCandidate:
    """One candidate to rank. ``key`` is a stable id used to merge results."""

    key: str
    full_name: str | None
    headline: str | None
    current_title: str | None
    current_company: str | None
    location: str | None
    skills: list[str] = field(default_factory=list)
    source: str = "linkedin"

    def text_blob(self) -> str:
        return " ".join(
            filter(
                None,
                [
                    self.full_name,
                    self.headline,
                    self.current_title,
                    self.current_company,
                    self.location,
                    " ".join(self.skills or []),
                ],
            )
        )


@dataclass
class RankedTalent:
    key: str
    score: float
    explanation: str
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)


# ── Agentic retrieval: distill a search query ────────────────────────────


_DISTILL_SYSTEM = (
    "You convert a recruiter's requirements brief into a SHORT LinkedIn "
    "people-search query (2-6 words) that surfaces the right candidates. "
    "Prefer the core role title plus 1-2 defining skills. No boolean "
    "operators, no long skill lists, no punctuation dumps. Reply with a single "
    'JSON object: {"search_query": "..."}'
)


def distill_search_query(text: str, *, job_title: str | None = None) -> str:
    """Turn a long requirements/skills brief into concise LinkedIn keywords.

    LinkedIn people-search expects a short keyword phrase, not a paragraph, so
    an over-long query returns nothing. The agent extracts the core role plus a
    couple of defining skills; a short query is used as-is. Falls back to the
    job title / first salient words when the LLM is unavailable.
    """
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return (job_title or "").strip()
    # Already short enough to search LinkedIn directly.
    if len(cleaned) <= 60 and "\n" not in (text or ""):
        return cleaned
    if settings.openrouter_api_key:
        try:
            data = generate_json_response(
                _DISTILL_SYSTEM,
                f"Job title (if known): {job_title or '—'}\n\n"
                f"Requirements / skills brief:\n{cleaned[:4000]}\n\n"
                "Return the JSON now.",
                model=settings.candidate_sourcing_reasoning_model,
                temperature=0.1,
                max_tokens=120,
            )
            q = str((data or {}).get("search_query") or "").strip()
            if q:
                return q[:200]
        except Exception:  # noqa: BLE001
            logger.warning("[FindTalent] query distillation failed; using fallback")
    return _fallback_keywords(cleaned, job_title)


def _fallback_keywords(text: str, job_title: str | None) -> str:
    if job_title and job_title.strip():
        return job_title.strip()[:120]
    words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 2]
    return " ".join(words[:6]) or text[:120]


# ── Public API ───────────────────────────────────────────────────────────


def rank_candidates(
    db: Session,
    *,
    candidates: list[TalentCandidate],
    query: str,
    job_id: UUID | None = None,
) -> list[RankedTalent]:
    """Return candidates ranked best-first against the job (or the query)."""
    if not candidates:
        return []

    job_ctx = _job_context(db, job_id) if job_id else None

    ranked: list[RankedTalent] | None = None
    if settings.openrouter_api_key:
        try:
            ranked = _rank_with_llm(candidates, query=query, job_ctx=job_ctx)
        except OpenRouterClientError as exc:
            logger.warning("[FindTalent] ranking LLM failed: %s", exc)
        except Exception:  # noqa: BLE001
            logger.exception("[FindTalent] ranking LLM unexpected error")

    if not ranked:
        ranked = _rank_deterministic(candidates, query=query, job_ctx=job_ctx)

    by_key = {r.key: r for r in ranked}
    # Ensure every candidate is represented, even if the LLM dropped some.
    for c in candidates:
        if c.key not in by_key:
            by_key[c.key] = _fallback_one(c, query=query, job_ctx=job_ctx)
    out = list(by_key.values())
    out.sort(key=lambda r: r.score, reverse=True)
    return out


# ── LLM ranking ──────────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are PATHS, a technical sourcing assistant. You receive a target role "
    "and a list of candidates sourced from LinkedIn and an internal database. "
    "Rank how well each candidate fits the role using only the evidence given "
    "(title, headline, company, location, skills). Be decisive and avoid bias "
    "(no inferences about gender, age, ethnicity, or nationality). Reply with a "
    "SINGLE valid JSON object and nothing else:\n"
    "{\n"
    '  "rankings": [\n'
    '    {"id": "<candidate id>", "score": <0-100 integer>, '
    '"explanation": "1-2 sentence why-this-match", '
    '"matched_skills": ["..."], "missing_skills": ["..."]}\n'
    "  ]\n"
    "}\n"
    "Score 80-100 = strong fit, 55-79 = possible fit, below 55 = weak fit."
)


def _rank_with_llm(
    candidates: list[TalentCandidate],
    *,
    query: str,
    job_ctx: dict[str, Any] | None,
) -> list[RankedTalent]:
    role_block = _role_block(query=query, job_ctx=job_ctx)
    cand_lines = []
    for c in candidates:
        cand_lines.append(
            json.dumps(
                {
                    "id": c.key,
                    "name": c.full_name,
                    "title": c.current_title or c.headline,
                    "headline": c.headline,
                    "company": c.current_company,
                    "location": c.location,
                    "skills": (c.skills or [])[:20],
                    "source": c.source,
                },
                ensure_ascii=False,
            )
        )
    user_prompt = (
        f"{role_block}\n\nCANDIDATES (rank all of them):\n"
        + "\n".join(cand_lines)
        + "\n\nReturn the JSON object now."
    )

    data = generate_json_response(
        _SYSTEM_PROMPT,
        user_prompt,
        model=settings.candidate_sourcing_reasoning_model,
        temperature=0.2,
        max_tokens=1800,
    )
    rankings = data.get("rankings") if isinstance(data, dict) else None
    if not isinstance(rankings, list):
        raise OpenRouterClientError("ranking response missing 'rankings' array")

    valid_keys = {c.key for c in candidates}
    out: list[RankedTalent] = []
    for item in rankings:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or "")
        if key not in valid_keys:
            continue
        out.append(
            RankedTalent(
                key=key,
                score=_clamp_score(item.get("score")),
                explanation=str(item.get("explanation") or "").strip()[:600],
                matched_skills=_str_list(item.get("matched_skills")),
                missing_skills=_str_list(item.get("missing_skills")),
            )
        )
    return out


# ── Deterministic fallback ───────────────────────────────────────────────


def _rank_deterministic(
    candidates: list[TalentCandidate],
    *,
    query: str,
    job_ctx: dict[str, Any] | None,
) -> list[RankedTalent]:
    return [_fallback_one(c, query=query, job_ctx=job_ctx) for c in candidates]


def _fallback_one(
    c: TalentCandidate,
    *,
    query: str,
    job_ctx: dict[str, Any] | None,
) -> RankedTalent:
    target_terms = _terms(query)
    job_skills: set[str] = set()
    if job_ctx:
        target_terms |= _terms(job_ctx.get("title") or "")
        job_skills = {s.lower() for s in job_ctx.get("required_skills", [])}
        job_skills |= {s.lower() for s in job_ctx.get("preferred_skills", [])}
        target_terms |= {t for s in job_skills for t in _terms(s)}

    cand_terms = _terms(c.text_blob())
    cand_skills = {s.lower() for s in (c.skills or [])}

    overlap = target_terms & cand_terms
    term_score = (len(overlap) / max(1, len(target_terms))) if target_terms else 0.3

    matched_skills = sorted(job_skills & cand_skills)
    missing_skills = sorted(job_skills - cand_skills)
    skill_score = (
        len(matched_skills) / max(1, len(job_skills)) if job_skills else 0.0
    )

    score = round(100.0 * (0.65 * term_score + 0.35 * skill_score), 1)
    # Title keyword match is a strong signal even without a skills list.
    if job_ctx and job_ctx.get("title"):
        if _terms(job_ctx["title"]) & _terms(c.current_title or c.headline or ""):
            score = max(score, 60.0)
    # Floor at 0 (not a positive value): a candidate with no overlap at all is a
    # "zero fit" and is filtered out of Find Talent results upstream.
    score = max(0.0, min(99.0, score))

    why = (
        f"Title/keywords overlap with the role ({', '.join(sorted(overlap)[:5]) or 'partial match'})."
        if overlap
        else "Limited overlap with the target role based on available signals."
    )
    return RankedTalent(
        key=c.key,
        score=score,
        explanation=why,
        matched_skills=matched_skills[:8],
        missing_skills=missing_skills[:8],
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _job_context(db: Session, job_id: UUID) -> dict[str, Any] | None:
    profile = jobs_relational.get_job_full_profile(db, job_id)
    if profile is None:
        return None
    required: list[str] = []
    preferred: list[str] = []
    for jsr, skill in getattr(profile, "skill_requirements", []) or []:
        name = (
            (skill.normalized_name if skill else None)
            or getattr(jsr, "skill_name_normalized", None)
            or ""
        ).strip()
        if not name:
            continue
        (required if getattr(jsr, "is_required", False) else preferred).append(name)
    job = profile.job
    return {
        "title": job.title,
        "seniority": job.seniority_level,
        "summary": (job.summary or job.description_text or "")[:1200],
        "location": job.location_text,
        "required_skills": required,
        "preferred_skills": preferred,
    }


def _role_block(*, query: str, job_ctx: dict[str, Any] | None) -> str:
    if job_ctx:
        return (
            "TARGET ROLE:\n"
            f"- Title: {job_ctx.get('title') or '—'}\n"
            f"- Seniority: {job_ctx.get('seniority') or '—'}\n"
            f"- Location: {job_ctx.get('location') or '—'}\n"
            f"- Required skills: {', '.join(job_ctx.get('required_skills') or []) or '—'}\n"
            f"- Preferred skills: {', '.join(job_ctx.get('preferred_skills') or []) or '—'}\n"
            f"- Summary: {job_ctx.get('summary') or '—'}\n"
            f"- Recruiter requirements / search brief: {query or '—'}"
        )
    return (
        "TARGET (no job selected — rank against the requirements below):\n"
        f"- Recruiter requirements / search brief: {query or '—'}"
    )


def _terms(text: str | None) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) > 1}


def _clamp_score(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 50.0
    if v <= 1.0:
        v *= 100.0
    return round(max(0.0, min(100.0, v)), 1)


def _str_list(value: Any, *, limit: int = 10) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s)
        if len(out) >= limit:
            break
    return out
