"""Candidate-facing job matching service.

Powers the candidate portal dashboard "Top Matches for You" section.

Match score is a **blend**, not raw cosine. Pure embedding cosine over
nomic-embed text vectors is almost always positive (0.6–0.8) for *any* two
job-ish documents, so it cannot tell a relevant role from an irrelevant one
and inflates every score into the 80s. Skills must therefore dominate, the
title is a small tie-breaker, and the cosine is de-inflated and contributes
least (see ``_blended_score``):

    with an embedding:   score = 0.70 · skill_fit   (saturating skill overlap, 1 − e^(−n/2))
                               + 0.22 · title_fit   (Jaccard of stop-stripped title tokens)
                               + 0.08 · semantic    (de-inflated cosine: 0.55→0, 0.85→1)

    without an embedding: score = 0.75 · skill_fit + 0.25 · title_fit

so a job in an unrelated domain (no shared skills, no title overlap) sinks
below the threshold, while a genuine skills match rises. The percentage is
therefore explainable: it tracks how many of the candidate's real skills the
job needs.

Two entry points:
  * :pyfunc:`top_matching_jobs`  — best-fitting active jobs (score ≥ threshold).
  * :pyfunc:`explain_job_match`  — per-job narrative, reusing the JD coach.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateSkill
from app.db.models.job import Job
from app.services.jd_analysis import analyze_job_description_for_candidate
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Tokenisation helpers ────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*")
_TITLE_STOP = frozenset({
    "senior", "junior", "jr", "sr", "lead", "principal", "staff", "mid",
    "level", "engineer", "developer", "specialist", "manager", "associate",
    "consultant", "analyst", "intern", "i", "ii", "iii", "iv", "of", "the",
    "and", "for", "a", "an", "to", "in", "with", "at", "remote",
})


def _tokens(text: str) -> set[str]:
    return {m.group(0) for m in _TOKEN_RE.finditer((text or "").lower())}


def _title_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if len(t) > 1 and t not in _TITLE_STOP}


def _safe_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _candidate_vector(qs: QdrantService, candidate_id: UUID) -> list[float] | None:
    """Fetch the candidate's single embedding from the candidate collection."""
    try:
        records = qs.client.retrieve(
            collection_name=settings.qdrant_candidate_collection,
            ids=[str(candidate_id)],
            with_vectors=True,
            with_payload=False,
        )
    except Exception:  # noqa: BLE001
        logger.exception("[candidate_match] failed to fetch candidate vector")
        return None
    if not records:
        return None
    vec = records[0].vector
    if isinstance(vec, dict):  # named-vector collections → {"name": [...]}
        vec = next(iter(vec.values())) if vec else None
    if not vec:
        return None
    return [float(x) for x in vec]


def _candidate_signals(db: Session, candidate_id: UUID) -> tuple[list[str], set[str]]:
    """Return (skill list, title tokens) for the candidate."""
    cand = db.get(Candidate, candidate_id)

    skills: list[str] = []
    rows = db.execute(
        select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)
    ).scalars().all()
    for cs in rows:
        nm = getattr(getattr(cs, "skill", None), "normalized_name", None)
        if isinstance(nm, str) and nm.strip():
            skills.append(nm.strip().lower())
    if not skills and cand and isinstance(cand.skills, list):
        skills = [str(s).strip().lower() for s in cand.skills if str(s).strip()]
    skills = sorted({s for s in skills if len(s) >= 2})

    title_toks: set[str] = set()
    if cand:
        title_toks |= _title_tokens(cand.current_title or "")
        if isinstance(getattr(cand, "desired_job_titles", None), list):
            for t in cand.desired_job_titles:
                title_toks |= _title_tokens(str(t))
    return skills, title_toks


def _job_text(job: Job) -> str:
    parts = [
        job.title or "", job.summary or "",
        job.description_text or "", job.requirements or "",
        job.role_family or "", job.seniority_level or "",
    ]
    return " ".join(parts).lower()[:6000]


def _match_skills(skills: list[str], job_text: str) -> list[str]:
    """Which of the candidate's skills the job text actually mentions."""
    matched: list[str] = []
    for sk in skills:
        if len(sk) <= 3:
            # short tokens (go, c, ml, r) need a word boundary to avoid
            # matching inside unrelated words (e.g. "ml" in "html").
            if re.search(rf"(?<![a-z0-9]){re.escape(sk)}(?![a-z0-9])", job_text):
                matched.append(sk)
        elif sk in job_text:
            matched.append(sk)
    return matched


def _salary_text(job: Job) -> str | None:
    if job.salary_min and job.salary_max:
        cur = job.salary_currency or "USD"
        return f"{cur} {int(job.salary_min):,} – {int(job.salary_max):,}"
    return None


# ── Scoring ─────────────────────────────────────────────────────────────────
# The percentage must be *honest*: skills are the primary, explainable signal;
# job title is only a small tie-breaker (sharing the word "backend" is NOT a
# 100% match); the semantic cosine — which sits at ~0.6–0.8 for almost any two
# job-ish documents — is de-inflated and contributes least. Combining additively
# (not max) means no single weak signal can pin the score at 100%.

def _skill_fit(matched_n: int) -> float:
    """Saturating skill score with diminishing returns:
    0→0%, 1→39%, 2→63%, 3→78%, 4→86%, 5→92%, 6→95%. So a couple of real skill
    matches already reads as a solid fit, while one shared skill stays modest
    and the curve never snaps to a flat 100%."""
    if matched_n <= 0:
        return 0.0
    return 1.0 - math.exp(-matched_n / 2.0)


def _title_jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard overlap of (stop-word-stripped) title tokens, 0..1."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _semantic_relevance(cosine: float) -> float:
    """De-inflate raw cosine: ~0.55 (generic similarity) → 0, ~0.85 → 1."""
    return max(0.0, min(1.0, (cosine - 0.55) / 0.30))


def _blended_score(matched_n: int, title_fit: float, cosine: float | None) -> int:
    """0–100 match score. Skills dominate; a same-role title adds a real bonus;
    semantic (when present) is a small de-inflated lift. Combined additively so
    no single weak signal pins the score — but a genuine fit (a few relevant
    skills + the right role) lands comfortably in the 75–90% band."""
    skill_fit = _skill_fit(matched_n)
    if cosine is None:
        relevance = 0.75 * skill_fit + 0.25 * title_fit
    else:
        relevance = (
            0.70 * skill_fit
            + 0.22 * title_fit
            + 0.08 * _semantic_relevance(cosine)
        )
    return round(100 * max(0.0, min(1.0, relevance)))


def _to_payload(
    job: Job, score: int, matched: list[str], applied_ids: set[str],
) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "title": job.title,
        "company_name": job.company_name,
        "location_text": job.location_text,
        "workplace_type": job.workplace_type,
        "seniority_level": job.seniority_level,
        "salary_text": _salary_text(job),
        "match_score": int(score),
        "matched_skills": matched[:6],
        "application_mode": job.application_mode,
        "external_apply_url": job.external_apply_url,
        "source_url": job.source_url,
        "source": job.source_platform or job.source_type,
        "already_applied": str(job.id) in applied_ids,
    }


def _applied_job_ids(db: Session, candidate_id: UUID) -> set[str]:
    return {
        str(jid)
        for (jid,) in db.execute(
            select(Application.job_id).where(Application.candidate_id == candidate_id)
        ).all()
    }


def _fallback_skill_match(
    db: Session, candidate_id: UUID, min_score: float, limit: int,
) -> list[dict[str, Any]]:
    """Skills/title-based matching used when the candidate has no embedding yet.

    The semantic vector is only created by the heavyweight ingestion pipeline.
    A candidate onboarded via the lightweight CV-extract flow has skills on their
    record but no vector — so rather than show zero matches, we rank active jobs
    purely on how many of the candidate's real skills (and target title) each job
    mentions. Score = 100 · max(skill_overlap, title_overlap).
    """
    skills, cand_title_toks = _candidate_signals(db, candidate_id)
    if not skills and not cand_title_toks:
        return []

    applied_ids = _applied_job_ids(db, candidate_id)

    jobs = db.execute(
        select(Job)
        .where(Job.is_active.is_(True))
        .order_by(Job.posted_at.desc().nullslast())
        .limit(300)
    ).scalars().all()

    scored: list[dict[str, Any]] = []
    for job in jobs:
        job_text = _job_text(job)
        matched = _match_skills(skills, job_text) if skills else []
        title_fit = _title_jaccard(cand_title_toks, _title_tokens(job.title or ""))
        score = _blended_score(len(matched), title_fit, cosine=None)
        if score < min_score:
            continue
        scored.append(_to_payload(job, score, matched, applied_ids))

    scored.sort(key=lambda r: r["match_score"], reverse=True)
    return scored[:limit]


def top_matching_jobs(
    db: Session,
    *,
    candidate_id: UUID,
    min_score: float = 50.0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the candidate's best-matching *active* jobs (blended score ≥ min_score).

    Empty list when the candidate has no embedding yet (CV not ingested) or
    nothing clears the threshold — the UI renders an empty state.
    """
    qs = QdrantService()
    cand_vec = _candidate_vector(qs, candidate_id)
    if not cand_vec:
        # No embedding (lightweight CV-extract onboarding) → skills/title match.
        return _fallback_skill_match(db, candidate_id, min_score, limit)

    # Over-fetch a generous candidate set; the blended re-rank below decides
    # the final order, so we must not rely on raw cosine order/cutoff.
    try:
        hits = qs.search_vectors(
            settings.qdrant_job_collection, cand_vec, limit=max(limit * 12, 60),
        )
    except Exception:  # noqa: BLE001
        logger.exception("[candidate_match] job vector search failed")
        return _fallback_skill_match(db, candidate_id, min_score, limit)

    skills, cand_title_toks = _candidate_signals(db, candidate_id)

    applied_ids = _applied_job_ids(db, candidate_id)

    scored: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        job_uuid = _safe_uuid(hit["id"])
        if job_uuid is None or str(job_uuid) in seen:
            continue
        job = db.get(Job, job_uuid)
        if job is None or not job.is_active:
            continue
        seen.add(str(job_uuid))

        sem = max(0.0, min(1.0, float(hit["score"])))
        job_text = _job_text(job)
        matched = _match_skills(skills, job_text) if skills else []
        title_fit = _title_jaccard(cand_title_toks, _title_tokens(job.title or ""))

        # Skills lead, title is a small bonus, de-inflated cosine contributes
        # least (see _blended_score) — so the % tracks real skill overlap and
        # off-domain roles sink instead of riding the cosine floor to the 80s.
        score = _blended_score(len(matched), title_fit, cosine=sem)
        if score < min_score:
            continue

        scored.append(_to_payload(job, score, matched, applied_ids))

    scored.sort(key=lambda r: r["match_score"], reverse=True)
    return scored[:limit]


def candidate_job_match_score(
    db: Session, *, candidate_id: UUID, job: Job,
) -> tuple[int, list[str]] | None:
    """The candidate↔job fit, computed the *same way* the candidate dashboard
    shows it (skills lead, title is a bonus). Returns ``(score, matched_skills)``
    so recruiters get the candidate's "initial intuition" fit % for this job, or
    ``None`` when the candidate has no skills/target title to match on."""
    skills, cand_title_toks = _candidate_signals(db, candidate_id)
    if not skills and not cand_title_toks:
        return None
    matched = _match_skills(skills, _job_text(job)) if skills else []
    title_fit = _title_jaccard(cand_title_toks, _title_tokens(job.title or ""))
    return _blended_score(len(matched), title_fit, cosine=None), matched[:6]


def explain_job_match(
    db: Session,
    *,
    candidate_id: UUID,
    job_id: UUID,
) -> dict[str, Any]:
    """Explain why a job matches the candidate, reusing the JD-analysis coach."""
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError("job_not_found")

    parts: list[str] = [job.title or ""]
    if job.company_name:
        parts.append(f"Company: {job.company_name}")
    if job.seniority_level:
        parts.append(f"Seniority: {job.seniority_level}")
    if job.location_text:
        parts.append(f"Location: {job.location_text}")
    body = (job.description_text or job.summary or "").strip()
    if body:
        parts.append(body)
    if job.requirements:
        parts.append("Requirements:\n" + job.requirements)
    jd_text = "\n\n".join(p for p in parts if p).strip()

    # The JD coach requires ≥30 chars — synthesise a minimal description for
    # sparse jobs so the explanation never 400s.
    if len(jd_text) < 30:
        jd_text = (
            f"{job.title or 'This role'} at "
            f"{job.company_name or 'the company'} — "
            f"{job.seniority_level or 'open'} level position"
            f"{f' based in {job.location_text}' if job.location_text else ''}."
        )

    return analyze_job_description_for_candidate(
        db, candidate_id=candidate_id, job_description_text=jd_text,
    )


__all__ = ["top_matching_jobs", "explain_job_match", "candidate_job_match_score"]
