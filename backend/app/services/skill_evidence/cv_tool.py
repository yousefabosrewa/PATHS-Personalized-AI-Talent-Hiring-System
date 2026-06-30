"""
CV evidence tool — pulls verifying snippets from the candidate's stored
CV data (Candidate row, experiences, certifications, raw CV blob).

This is the "candidate-cv" MCP-style tool in the brief's vocabulary:
the agent calls it with a skill and gets back any text in the
candidate's CV that mentions the skill, plus the years_used /
proficiency_score hints the ingestion agent extracted earlier.

Why have a CV tool at all when the data is already in our DB? Because
the evidence agent needs an evenly-shaped view across CV / GitHub /
LinkedIn. Giving the CV its own ``EvidenceResult`` lets the LLM score
each source independently and lets the UI render a per-source
breakdown the same way for all three.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateCertification, CandidateExperience
from app.services.skill_evidence.types import EvidenceResult, EvidenceSnippet

logger = logging.getLogger(__name__)


# How many characters of context to pull around each match. Tuned for
# LLM cost — wide enough to give the model real signal, narrow enough
# that 10 matches still fit in a single prompt.
_CONTEXT_WINDOW = 220


class CVEvidenceTool:
    """MCP-style tool that mines CV evidence for a single skill."""

    source = "cv"

    def __init__(self, db: Session) -> None:
        self._db = db

    def gather_evidence(
        self,
        *,
        candidate_id: uuid.UUID,
        skill: str,
    ) -> EvidenceResult:
        cand = self._db.get(Candidate, candidate_id)
        if cand is None:
            return EvidenceResult(
                source="cv",
                status="error",
                snippets=[],
                reason="Candidate not found.",
            )

        s = (skill or "").strip()
        if not s:
            return EvidenceResult(
                source="cv",
                status="error",
                snippets=[],
                reason="Empty skill.",
            )

        snippets: list[EvidenceSnippet] = []

        # ── Candidate-level signals ─────────────────────────────────
        self._scan_text(snippets, "summary", cand.summary, skill=s)
        self._scan_text(snippets, "headline", cand.headline, skill=s)
        self._scan_text(snippets, "current_title", cand.current_title, skill=s)

        # ── Experiences ─────────────────────────────────────────────
        experiences = list(
            self._db.execute(
                select(CandidateExperience)
                .where(CandidateExperience.candidate_id == candidate_id)
                .order_by(CandidateExperience.created_at.desc())
                .limit(20)
            ).scalars().all()
        )
        for exp in experiences:
            label = f"experience:{exp.company_name} — {exp.title}"
            self._scan_text(snippets, label, exp.description, skill=s, source_url=None)
            # Title often carries the skill name directly (e.g. "Python Developer").
            self._scan_text(snippets, f"role:{label}", exp.title, skill=s)

        # ── Certifications ─────────────────────────────────────────
        certs = list(
            self._db.execute(
                select(CandidateCertification)
                .where(CandidateCertification.candidate_id == candidate_id)
                .limit(20)
            ).scalars().all()
        )
        for c in certs:
            blob = " ".join(filter(None, [c.name, c.issuer]))
            self._scan_text(snippets, f"certification:{c.name}", blob, skill=s)

        # ── Skills array (raw stored on Candidate.skills) ──────────
        for raw_skill in (cand.skills or []):
            if not isinstance(raw_skill, str):
                continue
            if self._skill_matches(raw_skill, s):
                snippets.append(
                    EvidenceSnippet(
                        text=f"Skill listed on profile: {raw_skill}",
                        source_url=None,
                        weight_hint=0.6,
                        metadata={"source_field": "candidate.skills"},
                    )
                )

        if not snippets:
            return EvidenceResult(
                source="cv",
                status="no_match",
                snippets=[],
                reason=(
                    "The candidate's CV does not mention this skill in their "
                    "summary, experiences, or certifications."
                ),
            )

        return EvidenceResult(
            source="cv",
            status="available",
            snippets=snippets[:12],  # cap so the LLM prompt stays compact
            reason="",
            raw={
                "experience_count": len(experiences),
                "certification_count": len(certs),
            },
        )

    # ── Internals ───────────────────────────────────────────────────

    @staticmethod
    def _skill_matches(haystack: str, skill: str) -> bool:
        """Substring match, but respect word boundaries so ``Java`` doesn't
        match ``JavaScript`` (and vice-versa). Case-insensitive."""
        h = (haystack or "").lower()
        s = skill.lower()
        if not h or not s:
            return False
        # ``re.escape`` so skills with punctuation (e.g. C++ / .NET) work.
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(s)}(?![A-Za-z0-9+#.])"
        return re.search(pattern, h) is not None

    def _scan_text(
        self,
        snippets: list[EvidenceSnippet],
        label: str,
        text: str | None,
        *,
        skill: str,
        source_url: str | None = None,
    ) -> None:
        if not text:
            return
        if not self._skill_matches(text, skill):
            return
        # Extract a small window around the first occurrence so the LLM
        # gets context, not just the token.
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(skill)}(?![A-Za-z0-9+#.])"
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m is None:
            return
        start = max(0, m.start() - _CONTEXT_WINDOW // 2)
        end = min(len(text), m.end() + _CONTEXT_WINDOW // 2)
        snippet = text[start:end].strip()
        snippets.append(
            EvidenceSnippet(
                text=f"[{label}] …{snippet}…",
                source_url=source_url,
                weight_hint=1.0,
                metadata={"label": label, "match_start": m.start()},
            )
        )
