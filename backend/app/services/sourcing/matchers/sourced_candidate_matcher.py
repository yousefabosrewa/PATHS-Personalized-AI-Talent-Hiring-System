"""
PATHS Backend — Sourced-candidate matcher.

Ranks sourced (open-to-work) candidates against a single job using:

  1. Qdrant vector similarity (existing
     ``app.services.scoring.vector_similarity_service``) when both the
     candidate and the job already have a vector.
  2. Skill overlap (deterministic, dictionary-normalized).
  3. Soft filters: location, workplace setting, employment type.

The matcher reuses the existing one-vector-per-entity Qdrant collection
and never modifies it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate
from app.db.models.evidence import CandidateSource
from app.db.repositories import candidates_relational, jobs_relational
from app.services.scoring.vector_similarity_service import compute_similarity_score

logger = logging.getLogger(__name__)


# ── Result containers ────────────────────────────────────────────────────


@dataclass
class SourcedCandidateMatch:
    candidate_id: UUID
    score: float                 # 0..100 final score (vector + skill blend)
    vector_score: float          # 0..100 cosine-derived
    skill_overlap_score: float   # 0..100 deterministic skill overlap
    matched_skills: list[str] = field(default_factory=list)
    missing_required_skills: list[str] = field(default_factory=list)
    candidate: dict[str, Any] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    workplace_match: bool = True
    location_match: bool = True


# ── Public API ───────────────────────────────────────────────────────────


def rank_sourced_candidates_for_job(
    db: Session,
    *,
    job_id: UUID,
    candidate_ids: list[UUID],
    top_k: int = 20,
    workplace_settings: list[str] | None = None,
    location: str | None = None,
    employment_types: list[str] | None = None,
    min_score: float = 0.0,
    vector_weight: float = 0.6,
) -> list[SourcedCandidateMatch]:
    """Return up to ``top_k`` ranked matches for a sourced-candidate pool."""

    if not candidate_ids:
        return []

    job_profile = jobs_relational.get_job_full_profile(db, job_id)
    if job_profile is None:
        logger.warning("[SourcedMatcher] job %s not found", job_id)
        return []

    required_skills = _job_required_skills(job_profile)
    preferred_skills = _job_preferred_skills(job_profile)
    job_workplace = (job_profile.job.workplace_type or job_profile.job.location_mode or "").lower() or None
    job_location_blob = " ".join(
        filter(
            None,
            [
                (job_profile.job.location_text or ""),
                (job_profile.job.city or ""),
                (job_profile.job.country_code or ""),
            ],
        )
    ).lower()

    workplace_filter = {w.strip().lower() for w in (workplace_settings or []) if w}
    employment_filter = {e.strip().lower() for e in (employment_types or []) if e}
    location_filter = (location or "").strip().lower() or None

    matches: list[SourcedCandidateMatch] = []
    for cid in candidate_ids:
        c_profile = candidates_relational.get_candidate_full_profile(db, cid)
        if c_profile is None:
            continue
        c = c_profile.candidate

        # Soft filters (skip silently when they do not match the request)
        if employment_filter:
            cand_types = {x.lower() for x in (c.open_to_job_types or []) if isinstance(x, str)}
            if cand_types and not (cand_types & employment_filter):
                continue

        cand_workplace = {x.lower() for x in (c.open_to_workplace_settings or []) if isinstance(x, str)}
        workplace_match = True
        if workplace_filter:
            if cand_workplace and not (cand_workplace & workplace_filter):
                continue

        location_match = True
        if location_filter:
            cand_loc = (c.location_text or "").lower()
            if cand_loc and location_filter not in cand_loc:
                location_match = False

        # Compute vector similarity (returns 0.0 if vector missing)
        sim = compute_similarity_score(cid, job_id)
        vector_score = float(sim.score)

        # Skill overlap
        cand_skills = _candidate_skill_set(c, c_profile)
        matched, missing = _skill_overlap(cand_skills, required_skills)
        skill_score = _skill_score(cand_skills, required_skills, preferred_skills)

        # Final blend (vector_weight in [0,1])
        vw = max(0.0, min(1.0, float(vector_weight)))
        final = round(vector_score * vw + skill_score * (1.0 - vw), 3)

        if final < float(min_score):
            continue

        # Compute workplace alignment hint (informational only)
        if job_workplace and cand_workplace:
            workplace_match = job_workplace in cand_workplace

        if job_location_blob and (c.location_text or "").lower():
            cand_loc = (c.location_text or "").lower()
            location_match = location_match and (
                any(part for part in cand_loc.split(",") if part.strip() in job_location_blob)
                or any(part for part in job_location_blob.split(",") if part.strip() in cand_loc)
            )

        source_meta = _candidate_source_meta(db, cid)

        matches.append(
            SourcedCandidateMatch(
                candidate_id=cid,
                score=final,
                vector_score=vector_score,
                skill_overlap_score=skill_score,
                matched_skills=sorted(matched),
                missing_required_skills=sorted(missing),
                candidate=_candidate_summary_dict(c),
                source=source_meta,
                workplace_match=workplace_match,
                location_match=location_match,
            )
        )

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[: max(1, int(top_k))]


# ── Helpers ──────────────────────────────────────────────────────────────


def _job_required_skills(profile) -> set[str]:
    out: set[str] = set()
    for jsr, skill in profile.skill_requirements:
        if not jsr.is_required:
            continue
        name = (
            (skill.normalized_name if skill else None)
            or jsr.skill_name_normalized
            or ""
        ).lower().strip()
        if name:
            out.add(name)
    return out


def _job_preferred_skills(profile) -> set[str]:
    out: set[str] = set()
    for jsr, skill in profile.skill_requirements:
        if jsr.is_required:
            continue
        name = (
            (skill.normalized_name if skill else None)
            or jsr.skill_name_normalized
            or ""
        ).lower().strip()
        if name:
            out.add(name)
    return out


def _candidate_skill_set(c: Candidate, profile) -> set[str]:
    direct = {s.lower() for s in (c.skills or []) if isinstance(s, str)}
    structured = {
        (sk.normalized_name or "").lower()
        for _, sk in (profile.skills or [])
        if sk and sk.normalized_name
    }
    return {s for s in (direct | structured) if s}


def _skill_overlap(
    cand_skills: set[str], required: set[str],
) -> tuple[set[str], set[str]]:
    matched = cand_skills & required
    missing = required - cand_skills
    return matched, missing


def _skill_score(
    cand: set[str], required: set[str], preferred: set[str],
) -> float:
    if not required and not preferred:
        return 0.0
    score = 0.0
    if required:
        score += 70.0 * (len(cand & required) / max(1, len(required)))
    else:
        score += 40.0  # neutral baseline when no required list available
    if preferred:
        score += 30.0 * (len(cand & preferred) / max(1, len(preferred)))
    return round(min(100.0, score), 3)


def _candidate_summary_dict(c: Candidate) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "full_name": c.full_name,
        "headline": c.headline,
        "current_title": c.current_title,
        "location_text": c.location_text,
        "years_experience": c.years_experience,
        "skills": list(c.skills or []),
        "open_to_job_types": list(c.open_to_job_types or []),
        "open_to_workplace_settings": list(c.open_to_workplace_settings or []),
        "desired_job_titles": list(c.desired_job_titles or []),
        "summary": c.summary,
        "status": c.status,
    }


def _candidate_source_meta(db: Session, candidate_id: UUID) -> dict[str, Any]:
    row = (
        db.query(CandidateSource)
        .filter(CandidateSource.candidate_id == candidate_id)
        .order_by(CandidateSource.created_at.desc())
        .first()
    )
    if row is None:
        return {}
    return {
        "source": row.source,
        "url": row.url,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }
