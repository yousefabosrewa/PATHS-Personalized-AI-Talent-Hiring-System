"""PATHS Outreach Agent — search + anonymized agent explanation (fix4.md).

Two source modes are supported:

  * ``"database"`` — candidates already on the platform (signed-up profiles,
    CSV imports, manual entries). Matches the union used by
    ``/api/v1/sourcing/database-candidates``.
  * ``"outbound"`` — externally sourced candidates (LinkedIn Open-to-Work and
    similar providers). Matches the pool used by
    ``/api/v1/organization-candidate-sourcing/candidates``.

The search itself is deliberately lightweight (skill / title / location
overlap) — heavy vector search lives in the matching service and is not
required for an outreach shortlist. Every shortlisted candidate is then
anonymized and passed to the OpenRouter-backed agent for an explanation;
when the agent is unavailable, a deterministic fallback is produced so the
UI never breaks.

NO real name, email, phone, photo, LinkedIn, GitHub, or portfolio URL ever
leaves this module in the returned shortlist. ``candidate_id`` is the
opaque UUID — the caller may pass it to the existing approved
de-anonymization workflow later, never directly to the UI.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateExperience
from app.db.models.evidence import CandidateSource
from app.db.models.job import Job

logger = logging.getLogger(__name__)


OutreachMode = Literal["database", "outbound"]


# Source-type values that count as "internal" candidates already on the
# platform. Mirrors ``_INTERNAL_SOURCE_TYPES`` in :mod:`app.api.v1.sourcing`
# and ``_INTERNAL_POOL_SOURCE_TYPES`` in
# :mod:`app.api.v1.organization_candidate_sourcing`.
_INTERNAL_SOURCE_TYPES: frozenset[str] = frozenset(
    {"paths_profile", "imported", "uploaded", "manual"}
)

# Source platforms that count as "outbound" / externally sourced.
_OUTBOUND_PLATFORMS: frozenset[str] = frozenset(
    {"mock", "linkedin_open_to_work", "openresume_open_to_work"}
)


# ── Public dataclass ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class OutreachShortlistItem:
    """Single row of the anonymized shortlist returned to the UI."""

    candidate_id: str        # opaque UUID, NOT displayed by default
    alias: str               # e.g. "Candidate A-001"
    source: OutreachMode     # "database" | "outbound"
    match_score: int         # 0..100
    confidence: Literal["high", "medium", "low"]
    matched_skills: list[str]
    missing_skills: list[str]
    agent_explanation: str
    confidence_rationale: str
    risks_or_missing_evidence: str
    used_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "alias": self.alias,
            "source": self.source,
            "match_score": self.match_score,
            "confidence": self.confidence,
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
            "agent_explanation": self.agent_explanation,
            "confidence_rationale": self.confidence_rationale,
            "risks_or_missing_evidence": self.risks_or_missing_evidence,
            "used_fallback": self.used_fallback,
        }


# ── Alias helper ────────────────────────────────────────────────────────────


def candidate_alias(candidate_id: UUID | str, *, index: int | None = None) -> str:
    """Stable per-search alias.

    When ``index`` is given we format as ``"Candidate A-001"`` (matches the
    fix4 spec example). Otherwise we fall back to ``"Candidate ABCDEF"`` —
    the same six-hex format used by the Preparation agent.
    """
    if index is not None:
        return f"Candidate A-{index:03d}"
    s = str(candidate_id).replace("-", "").upper()
    return f"Candidate {s[:6]}"


# ── Query parsing ───────────────────────────────────────────────────────────


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,40}")


def _query_tokens(query: str) -> list[str]:
    """Lowercased keyword tokens from a free-text recruiter query."""
    return [m.group(0).lower() for m in _WORD_RE.finditer(query or "")]


def _resolve_required_skills(query: str, explicit_skills: list[str]) -> list[str]:
    """Final keyword list — explicit skills + meaningful query tokens."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in explicit_skills + _query_tokens(query):
        norm = raw.strip().lower()
        if not norm or norm in _STOPWORDS or norm in seen:
            continue
        seen.add(norm)
        out.append(raw.strip())
    return out


_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "the", "with", "for", "of", "in", "on", "at", "by",
    "or", "to", "from", "as", "is", "are", "be", "was", "were", "we",
    "looking", "experience", "engineer", "engineers", "developer",
    "developers", "candidate", "candidates", "role", "roles", "job",
    "needs", "need", "want", "seeking", "team",
})


# ── Candidate fetch + scoring ──────────────────────────────────────────────


def _fetch_internal_candidates(
    db: Session,
    *,
    org_id: UUID,
    limit: int = 200,
) -> list[Candidate]:
    """Internal candidates visible to this org (sourcing-page "database" pool)."""
    stmt = (
        select(Candidate)
        .where(
            or_(
                Candidate.source_type.is_(None),
                Candidate.source_type.in_(list(_INTERNAL_SOURCE_TYPES)),
            ),
            (Candidate.status == "active") | Candidate.status.is_(None),
            (Candidate.owner_organization_id.is_(None))
            | (Candidate.owner_organization_id == org_id),
        )
        .order_by(Candidate.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def _fetch_outbound_candidates(
    db: Session,
    *,
    org_id: UUID,
    limit: int = 200,
) -> list[Candidate]:
    """Externally sourced candidates (LinkedIn Open-to-Work etc.) for this org.

    We join ``CandidateSource`` so we only return rows that came from one of
    the outbound platforms. Org scoping mirrors the existing sourcing
    endpoint: either unowned or owned by this org.
    """
    stmt = (
        select(Candidate)
        .join(CandidateSource, CandidateSource.candidate_id == Candidate.id)
        .where(
            CandidateSource.source.in_(list(_OUTBOUND_PLATFORMS)),
            (Candidate.owner_organization_id.is_(None))
            | (Candidate.owner_organization_id == org_id),
        )
        .order_by(Candidate.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().unique().all())


def _score_candidate(
    cand: Candidate,
    *,
    required_keywords: list[str],
    seniority: str | None,
    workplace: str | None,
) -> tuple[int, list[str], list[str]]:
    """Cheap, deterministic relevance score in 0..100.

    Returns ``(score, matched_skills, missing_skills)``. Used to rank
    candidates inside a single mode — not a substitute for real vector
    similarity, just enough to surface plausible top-K rows for the agent
    to explain.
    """
    if not required_keywords:
        # Without a query we fall back to a generic recency score.
        return 50, [], []

    skill_set = {s.lower() for s in (cand.skills or []) if s}
    title = (cand.current_title or "").lower()
    headline = (cand.headline or "").lower()
    summary = (cand.summary or "").lower()

    matched: list[str] = []
    missing: list[str] = []
    for kw in required_keywords:
        k = kw.lower()
        if k in skill_set or k in title or k in headline or k in summary:
            matched.append(kw)
        else:
            missing.append(kw)

    base = int(round(100 * len(matched) / max(1, len(required_keywords))))

    if seniority and cand.career_level and seniority.lower() in (cand.career_level or "").lower():
        base = min(100, base + 5)
    if workplace:
        ws = {s.lower() for s in (cand.open_to_workplace_settings or [])}
        if workplace.lower() in ws:
            base = min(100, base + 3)

    return base, matched, missing


def _confidence_bucket(score: int, matched: int, total: int) -> Literal["high", "medium", "low"]:
    if total == 0:
        return "medium"
    ratio = matched / total
    if score >= 70 and ratio >= 0.6:
        return "high"
    if score >= 45 and ratio >= 0.35:
        return "medium"
    return "low"


# ── Anonymized evidence builder (agent input) ──────────────────────────────


_PII_FIELDS: frozenset[str] = frozenset({
    "full_name", "first_name", "last_name", "name",
    "email", "phone", "phone_number",
    "photo", "photo_url", "image", "image_url", "avatar", "avatar_url",
    "linkedin_url", "github_url", "portfolio_url",
})


def _anonymized_evidence(
    db: Session,
    cand: Candidate,
    *,
    alias: str,
    matched_skills: list[str],
    missing_skills: list[str],
) -> dict[str, Any]:
    """Build the dict the agent actually sees — NO personal identifiers."""
    # Recent experience titles only (employer names omitted).
    rows = db.execute(
        select(CandidateExperience.title)
        .where(CandidateExperience.candidate_id == cand.id)
        .order_by(CandidateExperience.created_at.desc())
        .limit(6)
    ).scalars().all()
    recent_titles = [t for t in rows if t]

    # Generalised location: drop street-level detail.
    location_general: str | None = None
    if cand.location_text:
        parts = [p.strip() for p in cand.location_text.split(",") if p.strip()]
        if len(parts) >= 2:
            location_general = ", ".join(parts[-2:])
        else:
            location_general = parts[0] if parts else None

    # Redact any literal occurrence of the candidate's name from free text.
    def _redact(text: str | None) -> str:
        if not text:
            return ""
        out = text
        for name_field in ("full_name", "first_name", "last_name"):
            val = getattr(cand, name_field, None)
            if isinstance(val, str) and val.strip():
                try:
                    out = re.sub(re.escape(val.strip()), "[REDACTED]", out, flags=re.IGNORECASE)
                except re.error:
                    pass
        return out[:1200]

    return {
        "alias":                alias,
        "current_role":         (cand.current_title or "").strip() or None,
        "years_experience":     cand.years_experience,
        "career_level":         cand.career_level,
        "location_general":     location_general,
        "skills_on_file":       list(cand.skills or [])[:30],
        "recent_role_titles":   recent_titles,
        "headline":             _redact(cand.headline),
        "summary":              _redact(cand.summary),
        "matched_keywords":     list(matched_skills),
        "unmatched_keywords":   list(missing_skills),
    }


# ── Agent prompt + JSON generation ─────────────────────────────────────────


_AGENT_SYSTEM = (
    "You are the PATHS Outreach Explanation Agent.\n\n"
    "Your task is to explain why an anonymized candidate was shortlisted "
    "for a recruiter search.\n\n"
    "Rules:\n"
    "  • Do not reveal or infer the candidate's real identity.\n"
    "  • Do not mention protected attributes (gender, religion, race, age, "
    "nationality, marital status, disability, political affiliation).\n"
    "  • Use only the provided evidence — never invent skills, employers, "
    "degrees, or experience.\n"
    "  • Be concise and recruiter-friendly (2-4 sentences for the main "
    "explanation).\n"
    "  • Mention strengths AND uncertainties. If evidence is missing, say "
    "so explicitly rather than guessing.\n"
    "  • Output ONLY a single JSON object matching the requested schema; "
    "no Markdown, no preamble, no trailing prose.\n"
)


_AGENT_SCHEMA = """{
  "agentExplanation": "<2-4 sentences explaining the fit, mentioning specific evidence>",
  "confidenceRationale": "<one sentence on why the confidence is high/medium/low>",
  "risksOrMissingEvidence": "<one sentence on gaps or unverified claims>"
}"""


def _run_agent(
    *,
    query: str,
    job_block: dict[str, Any],
    evidence: dict[str, Any],
    matching_signals: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Call the OpenRouter agent; return ``(payload, used_fallback)``.

    The fallback payload is deterministic and never references identity.
    """
    # Late import keeps this module importable when the LLM client has a
    # startup hiccup — explain_candidate has the same shape.
    try:
        from app.services.llm.openrouter_client import (
            OpenRouterClientError,
            generate_json_response,
        )
    except Exception as exc:  # pragma: no cover — safety net
        return _agent_fallback(evidence, matching_signals, reason=f"llm import failed: {exc}"), True

    user_prompt = (
        f"Recruiter Search Query:\n{(query or '').strip() or '(none)'}\n\n"
        f"Job / Search Context:\n{job_block or '(no job context)'}\n\n"
        f"Candidate Evidence (JSON, anonymized):\n{evidence}\n\n"
        f"Matching Signals (JSON):\n{matching_signals}\n\n"
        "Return JSON only matching this schema:\n"
        f"{_AGENT_SCHEMA}\n"
    )

    try:
        raw = generate_json_response(
            _AGENT_SYSTEM, user_prompt, temperature=0.15, max_tokens=480,
        )
    except OpenRouterClientError as exc:
        return _agent_fallback(evidence, matching_signals, reason=str(exc)[:120]), True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[OutreachAgent] generation failed: %s", exc)
        return _agent_fallback(evidence, matching_signals, reason="agent error"), True

    if not isinstance(raw, dict):
        return _agent_fallback(evidence, matching_signals, reason="non-object output"), True

    explanation = str(raw.get("agentExplanation") or "").strip()
    if not explanation:
        return _agent_fallback(evidence, matching_signals, reason="empty explanation"), True

    # Defensive sanitisation: strip any accidental identifiers the model
    # might have echoed back. The evidence we passed in is already redacted.
    explanation = _strip_pii_tokens(explanation)
    rationale = _strip_pii_tokens(str(raw.get("confidenceRationale") or "").strip())
    risks = _strip_pii_tokens(str(raw.get("risksOrMissingEvidence") or "").strip())

    return (
        {
            "agentExplanation": explanation,
            "confidenceRationale": rationale,
            "risksOrMissingEvidence": risks,
        },
        False,
    )


def _strip_pii_tokens(text: str) -> str:
    """Belt-and-braces guard: drop any obvious email/phone token from output."""
    if not text:
        return ""
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email redacted]", text)
    text = re.sub(r"\+?\d[\d\s().-]{7,}\d", "[phone redacted]", text)
    return text.strip()


def _agent_fallback(
    evidence: dict[str, Any],
    signals: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Deterministic explanation when the LLM is unavailable."""
    matched = evidence.get("matched_keywords") or []
    missing = evidence.get("unmatched_keywords") or []
    role = evidence.get("current_role")
    yrs = evidence.get("years_experience")

    bits: list[str] = []
    if matched:
        bits.append(f"matches the query through {', '.join(matched[:5])}")
    if role:
        bits.append(f"current role is {role}")
    if yrs:
        bits.append(f"around {yrs} years of experience")

    explanation = (
        f"{evidence.get('alias', 'This candidate')} was shortlisted because "
        + ("they " + "; ".join(bits) + "." if bits else
           "the profile has some overlap with the search query.")
    )

    score = signals.get("match_score", 0)
    conf = signals.get("confidence", "low")
    rationale = (
        f"Skill-overlap score of {score}/100 places this candidate in the "
        f"{conf}-confidence bucket. (Agent unavailable — fell back to "
        "deterministic explanation.)"
    )

    if missing:
        risks = (
            f"Evidence is missing for: {', '.join(missing[:5])}. "
            "Verify these in screening."
        )
    else:
        risks = (
            "No obvious keyword gap detected, but limited evidence in the "
            "profile — verify depth during a screening conversation."
        )

    return {
        "agentExplanation": explanation,
        "confidenceRationale": rationale,
        "risksOrMissingEvidence": risks + f" [reason: {reason[:80]}]",
    }


# ── Job-context helper ──────────────────────────────────────────────────────


def _job_block(db: Session, job_id: UUID | None) -> dict[str, Any]:
    if not job_id:
        return {}
    job = db.get(Job, job_id)
    if job is None:
        return {}
    return {
        "title":           getattr(job, "title", "") or "",
        "seniority_level": getattr(job, "seniority_level", "") or "",
        "summary":         (getattr(job, "summary", "") or "")[:500],
        "requirements":    (getattr(job, "requirements", "") or "")[:1000],
    }


# ── Entry point ─────────────────────────────────────────────────────────────


def run_outreach_search(
    db: Session,
    *,
    org_id: UUID,
    mode: OutreachMode,
    query: str,
    top_k: int = 8,
    job_id: UUID | None = None,
    required_skills: list[str] | None = None,
    seniority_level: str | None = None,
    workplace_type: str | None = None,
) -> dict[str, Any]:
    """Run an anonymized outreach search and generate per-candidate explanations.

    The returned dict is shaped for the frontend (fix4.md "Suggested Backend
    Response Shape"):

    ``{
        source_mode: "database" | "outbound",
        query: str,
        shortlist: [OutreachShortlistItem.to_dict()],
        agent_available: bool,            # false if every row used the fallback
    }``
    """
    if mode not in ("database", "outbound"):
        raise ValueError(f"unsupported outreach mode: {mode!r}")

    top_k = max(1, min(int(top_k or 8), 20))
    keywords = _resolve_required_skills(query, required_skills or [])

    candidates: list[Candidate]
    if mode == "database":
        candidates = _fetch_internal_candidates(db, org_id=org_id, limit=200)
    else:
        candidates = _fetch_outbound_candidates(db, org_id=org_id, limit=200)

    # Score + rank.
    scored: list[tuple[Candidate, int, list[str], list[str]]] = []
    for cand in candidates:
        score, matched, missing = _score_candidate(
            cand,
            required_keywords=keywords,
            seniority=seniority_level,
            workplace=workplace_type,
        )
        scored.append((cand, score, matched, missing))

    # Sort: highest score first, then candidates with at least one matched
    # keyword. Recency is the implicit tie-breaker from the SELECT order.
    scored.sort(key=lambda r: (r[1], len(r[2])), reverse=True)

    # Drop rows with zero overlap when the recruiter typed a real query —
    # they'd produce noisy explanations.
    if keywords:
        scored = [r for r in scored if r[2]]

    scored = scored[:top_k]

    if not scored:
        return {
            "source_mode": mode,
            "query": query,
            "shortlist": [],
            "agent_available": True,
        }

    job_block_dict = _job_block(db, job_id)

    items: list[OutreachShortlistItem] = []
    agent_failed_count = 0
    for idx, (cand, score, matched, missing) in enumerate(scored, start=1):
        alias = candidate_alias(cand.id, index=idx)
        evidence = _anonymized_evidence(
            db, cand, alias=alias, matched_skills=matched, missing_skills=missing,
        )
        bucket = _confidence_bucket(score, len(matched), len(keywords) or 1)
        signals = {
            "match_score": score,
            "confidence": bucket,
            "matched_skill_count": len(matched),
            "total_required": len(keywords),
        }
        agent_payload, used_fallback = _run_agent(
            query=query,
            job_block=job_block_dict,
            evidence=evidence,
            matching_signals=signals,
        )
        if used_fallback:
            agent_failed_count += 1

        items.append(
            OutreachShortlistItem(
                candidate_id=str(cand.id),
                alias=alias,
                source=mode,
                match_score=score,
                confidence=bucket,
                matched_skills=matched[:12],
                missing_skills=missing[:12],
                agent_explanation=str(agent_payload.get("agentExplanation", "")),
                confidence_rationale=str(agent_payload.get("confidenceRationale", "")),
                risks_or_missing_evidence=str(agent_payload.get("risksOrMissingEvidence", "")),
                used_fallback=used_fallback,
            )
        )

    return {
        "source_mode": mode,
        "query": query,
        "shortlist": [it.to_dict() for it in items],
        "agent_available": agent_failed_count < len(items),
    }


# ── Public re-export for convenience ───────────────────────────────────────


def _ensure_pii_invariant() -> None:
    """Static check used by tests — guards against accidental leak fields."""
    leaks = _PII_FIELDS & set(OutreachShortlistItem.__dataclass_fields__.keys())
    if leaks:  # pragma: no cover
        raise RuntimeError(f"OutreachShortlistItem leaks PII fields: {leaks}")


_ensure_pii_invariant()


# Silence unused-import warnings — kept around for future filters on
# applied/shortlisted state per job.
_ = Application
