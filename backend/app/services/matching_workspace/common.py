"""Shared helpers for the matching workspace (semantic search + RAG test).

Anonymization, candidate evidence builders, and the agent JSON contract
live here so both endpoints stay consistent.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate
from app.db.models.cv_entities import (
    CandidateEducation,
    CandidateExperience,
    CandidateSkill,
)

logger = logging.getLogger(__name__)


# ── Public types ────────────────────────────────────────────────────────────


CandidateSource = Literal["database", "outbound", "imported_csv", "unknown"]


@dataclass(frozen=True)
class EvidenceChunk:
    """One atomic piece of evidence retrieved from a candidate profile."""

    field: str          # e.g. "experience" | "project" | "skill" | "summary"
    text: str
    source_label: str   # short human-readable, e.g. "Recent role"
    score: float = 0.0  # cosine similarity to the query (set by RAG retriever)


# ── Alias helpers ───────────────────────────────────────────────────────────


def candidate_alias(candidate_id: UUID | str, *, index: int | None = None) -> str:
    """Stable per-call alias.

    With ``index`` we use the spec example format (``Candidate #A104``).
    Without it we fall back to the deterministic hex form used elsewhere
    in PATHS so cross-page links stay consistent.
    """
    if index is not None:
        return f"Candidate #A{index:03d}"
    s = str(candidate_id).replace("-", "").upper()
    return f"Candidate {s[:6]}"


def derive_source(cand: Candidate) -> CandidateSource:
    """Return a UI-friendly source label for a candidate row."""
    st = (cand.source_type or "").lower()
    if st in {"linkedin_open_to_work", "openresume_open_to_work", "mock"}:
        return "outbound"
    if st in {"imported", "csv_import"}:
        return "imported_csv"
    if st in {"paths_profile", "uploaded", "manual", ""}:
        return "database"
    return "unknown"


_SOURCE_DISPLAY: dict[str, str] = {
    "database":     "Database",
    "outbound":     "LinkedIn Open to Work",
    "imported_csv": "Imported CSV",
    "unknown":      "Unknown",
}


def source_display(source: CandidateSource) -> str:
    return _SOURCE_DISPLAY.get(source, "Unknown")


# ── Evidence builder ────────────────────────────────────────────────────────


def build_evidence_chunks(
    db: Session, candidate_id: UUID,
) -> list[EvidenceChunk]:
    """Build a list of small, retrievable evidence chunks for a candidate.

    Each chunk maps to one structured field (an experience, a project, a
    cluster of skills, the CV summary). Keeping them small lets the RAG
    retriever pick exactly the snippets relevant to a given requirement.
    """
    chunks: list[EvidenceChunk] = []

    cand = db.get(Candidate, candidate_id)
    if cand is None:
        return chunks

    # CV / profile summary
    if (cand.summary or "").strip():
        chunks.append(
            EvidenceChunk(
                field="summary",
                text=(cand.summary or "").strip()[:1200],
                source_label="Profile summary",
            )
        )
    if cand.headline:
        chunks.append(
            EvidenceChunk(
                field="headline",
                text=str(cand.headline)[:300],
                source_label="Headline",
            )
        )

    # Skills (grouped, not one-per-skill — too noisy)
    skill_names: list[str] = []
    rows = db.execute(
        select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)
    ).scalars().all()
    for cs in rows:
        sk_rel = getattr(cs, "skill", None)
        name = getattr(sk_rel, "normalized_name", None) if sk_rel else None
        if isinstance(name, str) and name.strip():
            skill_names.append(name.strip())
    if not skill_names and isinstance(cand.skills, list):
        skill_names = [str(s) for s in cand.skills if str(s).strip()]
    if skill_names:
        chunks.append(
            EvidenceChunk(
                field="skills",
                text="Skills on file: " + ", ".join(skill_names[:60]),
                source_label="Skills",
            )
        )

    # Experiences — one chunk per role
    exps = db.execute(
        select(CandidateExperience)
        .where(CandidateExperience.candidate_id == candidate_id)
        .order_by(CandidateExperience.start_date.desc().nullslast())
    ).scalars().all()
    for e in exps[:8]:
        title = getattr(e, "title", "") or ""
        desc = getattr(e, "description", "") or ""
        if not title and not desc:
            continue
        text_parts: list[str] = []
        if title:
            text_parts.append(f"Role: {title}")
        if desc:
            text_parts.append(desc.strip()[:1500])
        chunks.append(
            EvidenceChunk(
                field="experience",
                text="\n".join(text_parts),
                source_label=f"Experience — {title or 'role'}",
            )
        )

    # Education — compact one-liner so it can still match degree/field queries
    edus = db.execute(
        select(CandidateEducation)
        .where(CandidateEducation.candidate_id == candidate_id)
    ).scalars().all()
    edu_lines = [
        f"{(ed.degree or '').strip()} in {(ed.field_of_study or '').strip()}".strip()
        for ed in edus
        if (ed.degree or ed.field_of_study)
    ]
    if edu_lines:
        chunks.append(
            EvidenceChunk(
                field="education",
                text="Education: " + "; ".join(edu_lines[:4]),
                source_label="Education",
            )
        )

    return chunks


# ── Anonymized agent input ──────────────────────────────────────────────────


def anonymized_evidence_block(
    cand: Candidate,
    *,
    alias: str,
    extra_chunks: list[EvidenceChunk] | None = None,
) -> dict[str, Any]:
    """Build the dict the agent sees — never includes direct identifiers."""

    location_general: str | None = None
    if cand.location_text:
        parts = [p.strip() for p in cand.location_text.split(",") if p.strip()]
        if len(parts) >= 2:
            location_general = ", ".join(parts[-2:])
        else:
            location_general = parts[0] if parts else None

    return {
        "alias":             alias,
        "current_role":      (cand.current_title or "").strip() or None,
        "years_experience":  cand.years_experience,
        "career_level":      cand.career_level,
        "location_general":  location_general,
        "skills_on_file":    list(cand.skills or [])[:30],
        "headline":          (cand.headline or "")[:300] if cand.headline else None,
        "summary":           (cand.summary or "")[:800] if cand.summary else None,
        "retrieved_evidence": [
            {
                "field": c.field,
                "label": c.source_label,
                "text": c.text[:1000],
                "relevance": round(c.score, 4),
            }
            for c in (extra_chunks or [])
        ],
    }


# ── Safety: scrub PII tokens from agent output ──────────────────────────────


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def scrub_pii(text: str) -> str:
    if not text:
        return ""
    text = _EMAIL_RE.sub("[email redacted]", text)
    text = _PHONE_RE.sub("[phone redacted]", text)
    return text.strip()
