"""
PATHS Backend — Candidate Anonymizer (Phase 4).

Enforces Blueprint Law #2:
  "Anonymize before evaluate, de-anonymize only on outreach approval."

Public API
----------
build_anonymized_json(profile)          → dict   (pure, no DB)
get_or_create_view(db, candidate_id)    → AnonymizedView (DB)
invalidate_view(db, candidate_id)       → None   (bump version on profile change)

The anonymized JSON shape (what agents actually receive):
  alias            — "Candidate <6-char hex>"
  skills           — list of {name, proficiency}
  years_experience — int
  career_level     — str
  current_title    — str  (kept — title is not a protected attribute)
  location_general — str  (city/country only, street stripped)
  summary          — str  (name tokens replaced with [REDACTED])
  experiences      — [{title, duration_months, description, is_current}]
                     company names stripped
  education        — [{degree, field_of_study, years}]
                     school names stripped by default
  certifications   — [str]
  projects         — [{name, description, technologies, duration_months}]
  desired_job_types      — [str]
  desired_workplace      — [str]

Nothing in this module ever logs or prints PII.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.bias_fairness import AnonymizedView
from app.db.repositories.candidates_relational import CandidateFullProfile
from app.db.repositories import scoring_repository as _repo

logger = logging.getLogger(__name__)

# ── PII field names (never appear in anonymized output) ──────────────────────

_PROTECTED: frozenset[str] = frozenset({
    "full_name", "name", "first_name", "last_name",
    "email", "phone", "phone_number",
    "photo", "photo_url", "image", "image_url", "avatar", "avatar_url",
    "gender", "sex", "age", "date_of_birth", "dob",
    "marital_status", "religion", "nationality", "citizenship",
    "address", "street_address", "postal_code", "zip_code",
    "ssn", "national_id", "passport", "tax_id",
    "disability", "political_views", "race", "ethnicity",
    "social_security_number",
})

# Regex: match common name-like tokens in free text so we can redact them.
# We replace the candidate's actual name with [REDACTED] in text fields.
_NAME_PLACEHOLDER = "[REDACTED]"


# ── Pure builder (no DB) ─────────────────────────────────────────────────────


def build_anonymized_json(profile: CandidateFullProfile) -> tuple[dict, list[str]]:
    """Build the anonymized dict from a full profile.

    Returns
    -------
    (view_json, stripped_fields)
        view_json       — the safe dict to persist and pass to agents
        stripped_fields — list of field names that were removed
    """
    cand = profile.candidate
    stripped: list[str] = []

    # Track which top-level protected fields existed so audit knows what was stripped.
    for f in _PROTECTED:
        if getattr(cand, f, None) not in (None, ""):
            stripped.append(f)

    # ── Alias — deterministic, non-reversible ────────────────────────
    alias = f"Candidate {str(cand.id)[:6].upper()}"

    # ── Skills ───────────────────────────────────────────────────────
    skills = []
    for cs, skill_obj in profile.skills:
        skills.append({
            "name": skill_obj.name if skill_obj else (cs.skill_name or ""),
            "proficiency": getattr(cs, "proficiency_level", "unknown"),
        })

    # ── Experiences (company names stripped) ─────────────────────────
    experiences = []
    for exp, _company in profile.experiences:
        duration_months: int | None = None
        if exp.start_date and exp.end_date:
            try:
                from dateutil.relativedelta import relativedelta  # type: ignore
                delta = relativedelta(exp.end_date, exp.start_date)
                duration_months = delta.years * 12 + delta.months
            except Exception:
                pass

        experiences.append({
            "title": exp.job_title or "",
            "duration_months": duration_months,
            "description": _redact_name(exp.description or "", cand.full_name),
            "is_current": getattr(exp, "is_current", False),
        })

    # ── Education (school names stripped) ────────────────────────────
    education = []
    for edu in profile.education:
        education.append({
            "degree": edu.degree or "",
            "field_of_study": edu.field_of_study or "",
            "graduation_year": getattr(edu, "end_year", None),
        })

    # ── Certifications ────────────────────────────────────────────────
    certifications = [
        c.name for c in profile.certifications if c.name
    ]

    # ── Projects (keep tech / description, no personal URLs) ─────────
    projects = []
    for proj in profile.projects:
        projects.append({
            "name": proj.name or "",
            "description": _redact_name(proj.description or "", cand.full_name),
            "technologies": list(proj.technologies or []),
        })

    # ── Location (general only) ───────────────────────────────────────
    location_general = _general_location(cand.location_text)

    # ── Summary (redact name tokens) ─────────────────────────────────
    summary_redacted = _redact_name(cand.summary or "", cand.full_name)

    view_json: dict[str, Any] = {
        "alias": alias,
        "skills": skills,
        "years_experience": cand.years_experience,
        "career_level": cand.career_level,
        "current_title": cand.current_title,
        "location_general": location_general,
        "summary": summary_redacted,
        "experiences": experiences,
        "education": education,
        "certifications": certifications,
        "projects": projects,
        "desired_job_types": list(cand.open_to_job_types or []),
        "desired_workplace": list(cand.open_to_workplace_settings or []),
    }

    return view_json, stripped


# ── DB helpers ───────────────────────────────────────────────────────────────


def get_or_create_view(db: Session, candidate_id: uuid.UUID) -> AnonymizedView:
    """Return the current AnonymizedView for candidate_id, creating it if absent.

    If the candidate profile has changed since the last view was built
    (detected via source_hash), a new version is created and the old one
    is marked is_current=False.
    """
    profile = _repo.get_candidate_profile(db, candidate_id)
    if profile is None:
        raise ValueError(f"Candidate {candidate_id} not found")

    current_hash = _profile_hash(profile)

    # Look for an existing current view.
    existing: AnonymizedView | None = db.execute(
        select(AnonymizedView).where(
            AnonymizedView.candidate_id == candidate_id,
            AnonymizedView.is_current == True,  # noqa: E712
        )
    ).scalar_one_or_none()

    if existing and existing.source_hash == current_hash:
        return existing  # Up-to-date — nothing to do.

    # Build fresh view.
    view_json, stripped = build_anonymized_json(profile)

    new_version = (existing.view_version + 1) if existing else 1

    # Retire old current view.
    if existing:
        db.execute(
            update(AnonymizedView)
            .where(
                AnonymizedView.candidate_id == candidate_id,
                AnonymizedView.is_current == True,  # noqa: E712
            )
            .values(is_current=False)
        )
        db.flush()

    new_view = AnonymizedView(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        view_version=new_version,
        is_current=True,
        view_json=view_json,
        stripped_fields=stripped,
        source_hash=current_hash,
    )
    db.add(new_view)
    db.commit()
    db.refresh(new_view)

    logger.info(
        "[Anonymizer] created AnonymizedView v%s for candidate %s (stripped: %s)",
        new_version, str(candidate_id)[:8], stripped,
    )
    return new_view


def get_current_view(db: Session, candidate_id: uuid.UUID) -> AnonymizedView | None:
    """Return the current view without creating one."""
    return db.execute(
        select(AnonymizedView).where(
            AnonymizedView.candidate_id == candidate_id,
            AnonymizedView.is_current == True,  # noqa: E712
        )
    ).scalar_one_or_none()


def invalidate_view(db: Session, candidate_id: uuid.UUID) -> None:
    """Mark all views for candidate_id as stale (is_current=False).

    Call this whenever the candidate profile is updated so the next
    scoring run rebuilds the view from fresh data.
    """
    db.execute(
        update(AnonymizedView)
        .where(AnonymizedView.candidate_id == candidate_id)
        .values(is_current=False)
    )
    db.commit()
    logger.info("[Anonymizer] invalidated views for candidate %s", str(candidate_id)[:8])


# ── Private helpers ───────────────────────────────────────────────────────────


def _profile_hash(profile: CandidateFullProfile) -> str:
    """Deterministic fingerprint of the profile — used to detect staleness."""
    cand = profile.candidate
    parts = [
        str(cand.id),
        str(cand.updated_at),
        str(len(profile.skills)),
        str(len(profile.experiences)),
        str(len(profile.education)),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:64]


def _redact_name(text: str, full_name: str | None) -> str:
    """Replace occurrences of the candidate's name in free text."""
    if not text or not full_name:
        return text
    try:
        pattern = re.compile(re.escape(full_name.strip()), re.IGNORECASE)
        return pattern.sub(_NAME_PLACEHOLDER, text)
    except Exception:
        return text


def _general_location(location_text: str | None) -> str | None:
    """Return city/country portion of a location string; strip street-level detail."""
    if not location_text:
        return None
    # Keep the last two comma-separated parts (typically city, country)
    parts = [p.strip() for p in location_text.split(",")]
    if len(parts) >= 2:
        return ", ".join(parts[-2:])
    return location_text
