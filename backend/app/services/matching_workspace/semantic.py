"""Semantic candidate search using the existing Qdrant infrastructure (fix7.md).

Pipeline:

  1. Embed the recruiter query via Ollama (``nomic-embed-text``).
  2. Hit Qdrant's ``paths_candidates`` collection (one vector per candidate)
     to retrieve top-N similar candidate IDs + cosine scores.
  3. Load each candidate row from PostgreSQL, filter to candidates the
     calling org may legally see.
  4. For each, build the anonymized agent input and ask OpenRouter for a
     short explanation. The query and matched / missing signals are
     extracted heuristically and passed to the agent — the agent never
     invents skills.

Degradation modes:

  * Qdrant unreachable → fall back to a SQL keyword/skill overlap rank
    so HR still gets a meaningful shortlist; ``semantic_search_used`` is
    set to ``False`` in the response so the UI can warn.
  * Embedding model unreachable → same fallback.
  * LLM unreachable → per-row ``agent_explanation`` is empty and
    ``agent_available`` is ``False``; the UI then shows a safe message.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.candidate_access import org_can_view_candidate
from app.core.config import get_settings
from app.db.models.candidate import Candidate
from app.services.embedding_service import embed_query
from app.services.qdrant_service import QdrantService

from .common import (
    EvidenceChunk,
    anonymized_evidence_block,
    candidate_alias,
    derive_source,
    scrub_pii,
    source_display,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Public types ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SemanticSearchResult:
    """One row of the anonymized semantic-search shortlist."""

    candidate_id: str
    anonymized_label: str
    source: str
    source_display: str
    headline: str | None
    current_title: str | None
    semantic_score: int          # 0..100
    confidence: int              # 0..100
    matched_evidence: list[str]
    missing_signals: list[str]
    agent_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "anonymized_label": self.anonymized_label,
            "source": self.source,
            "source_display": self.source_display,
            "headline": self.headline,
            "current_title": self.current_title,
            "semantic_score": self.semantic_score,
            "confidence": self.confidence,
            "matched_evidence": list(self.matched_evidence),
            "missing_signals": list(self.missing_signals),
            "agent_explanation": self.agent_explanation,
        }


# ── Source filter ───────────────────────────────────────────────────────────


_INTERNAL_SOURCE_TYPES = frozenset({
    "paths_profile", "imported", "uploaded", "manual", "", None,
})
_OUTBOUND_SOURCE_TYPES = frozenset({
    "linkedin_open_to_work", "openresume_open_to_work", "mock",
})


def _matches_source_filter(cand: Candidate, source: str) -> bool:
    if source == "all":
        return True
    st = (cand.source_type or "").lower() or ""
    if source == "database":
        return st in _INTERNAL_SOURCE_TYPES or st == ""
    if source == "outbound":
        return st in _OUTBOUND_SOURCE_TYPES
    if source == "imported_csv":
        return st in {"imported", "csv_import"}
    return True


# ── Heuristic signal extraction ─────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,30}")
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "the", "with", "for", "of", "in", "on", "at", "by",
    "or", "to", "from", "as", "is", "are", "be", "was", "were", "we",
    "looking", "experience", "engineer", "engineers", "developer",
    "developers", "candidate", "candidates", "role", "roles", "job",
    "needs", "need", "want", "seeking", "team", "find", "search",
    "year", "years", "plus", "junior", "mid", "senior",
})


def _query_keywords(query: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _TOKEN_RE.finditer(query or ""):
        tok = m.group(0)
        norm = tok.lower()
        if norm in _STOPWORDS or norm in seen:
            continue
        seen.add(norm)
        out.append(tok)
    return out


def _candidate_signal_corpus(cand: Candidate) -> str:
    parts: list[str] = [
        (cand.current_title or ""),
        (cand.headline or ""),
        (cand.summary or ""),
    ]
    parts += [str(s) for s in (cand.skills or [])]
    return " | ".join(p for p in parts if p)


def _split_matched_missing(
    cand: Candidate, query_keywords: list[str],
) -> tuple[list[str], list[str]]:
    if not query_keywords:
        return [], []
    corpus = _candidate_signal_corpus(cand).lower()
    matched: list[str] = []
    missing: list[str] = []
    for kw in query_keywords:
        if kw.lower() in corpus:
            matched.append(f"{kw} found in profile")
        else:
            missing.append(f"No clear {kw} signal")
    return matched, missing


# ── Confidence ──────────────────────────────────────────────────────────────


def _confidence(
    *,
    semantic_score: int,
    matched: int,
    total: int,
    has_profile: bool,
) -> int:
    """Blend semantic similarity with structural evidence.

    Low when the profile is sparse or when keywords aren't reflected in
    structured fields, even if the vector score is high.
    """
    if total == 0:
        base = semantic_score
    else:
        coverage = matched / total
        base = round(0.6 * semantic_score + 0.4 * (coverage * 100))
    if not has_profile:
        base = int(base * 0.7)
    return max(0, min(100, int(base)))


# ── Fallback ranking (no Qdrant) ────────────────────────────────────────────


def _sql_fallback_rank(
    db: Session, *, org_id: UUID, query_keywords: list[str], limit: int,
) -> list[tuple[Candidate, int]]:
    """Skill / title / summary overlap rank — used when Qdrant is down."""
    stmt = (
        select(Candidate)
        .where(
            (Candidate.owner_organization_id.is_(None))
            | (Candidate.owner_organization_id == org_id),
            (Candidate.status == "active") | Candidate.status.is_(None),
        )
        .order_by(Candidate.created_at.desc())
        .limit(400)
    )
    if query_keywords:
        first_kw = query_keywords[0]
        needle = f"%{first_kw}%"
        stmt = stmt.where(
            or_(
                Candidate.current_title.ilike(needle),
                Candidate.headline.ilike(needle),
                Candidate.summary.ilike(needle),
            )
        )
    rows = list(db.execute(stmt).scalars().all())
    scored: list[tuple[Candidate, int]] = []
    for c in rows:
        corpus = _candidate_signal_corpus(c).lower()
        if not query_keywords:
            scored.append((c, 50))
            continue
        hits = sum(1 for kw in query_keywords if kw.lower() in corpus)
        score = round(100 * hits / max(1, len(query_keywords)))
        if hits == 0:
            continue
        scored.append((c, score))
    scored.sort(key=lambda r: r[1], reverse=True)
    return scored[:limit]


# ── Agent (OpenRouter) ──────────────────────────────────────────────────────


_AGENT_SYSTEM = (
    "You are the PATHS Semantic Search Explanation Agent.\n\n"
    "Explain, in 2-4 sentences, why this anonymized candidate matches a "
    "natural-language recruiter query, and what evidence is missing.\n\n"
    "Rules:\n"
    "  • Do not reveal or infer the candidate's real identity.\n"
    "  • Do not mention protected attributes.\n"
    "  • Use ONLY the provided structured evidence — never invent skills, "
    "employers, degrees, or experience.\n"
    "  • If evidence for a query term is missing, say so explicitly.\n"
    "  • Output ONLY a single JSON object: "
    '{"agentExplanation":"<text>"}.'
)


def _agent_explanation(
    *,
    query: str,
    evidence: dict[str, Any],
    matched: list[str],
    missing: list[str],
    semantic_score: int,
) -> tuple[str, bool]:
    """Return ``(explanation, used_fallback)``."""
    try:
        from app.services.llm.openrouter_client import (
            OpenRouterClientError,
            generate_json_response,
        )
    except Exception as exc:  # pragma: no cover - safety net
        logger.warning("openrouter import failed: %s", exc)
        return "", True

    user = (
        f"Recruiter query:\n{(query or '').strip() or '(empty)'}\n\n"
        f"Anonymized candidate evidence (JSON):\n{evidence}\n\n"
        f"Heuristic matched signals: {matched or '(none)'}\n"
        f"Heuristic missing signals: {missing or '(none)'}\n"
        f"Semantic similarity score (0-100): {semantic_score}\n\n"
        'Return JSON only: {"agentExplanation":"<2-4 sentences>"}.'
    )
    try:
        raw = generate_json_response(_AGENT_SYSTEM, user, temperature=0.2, max_tokens=300)
    except OpenRouterClientError as exc:
        logger.info("semantic_search agent unavailable: %s", str(exc)[:120])
        return "", True
    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic_search agent failed: %s", exc)
        return "", True

    if not isinstance(raw, dict):
        return "", True
    text = scrub_pii(str(raw.get("agentExplanation") or "").strip())
    return text, not bool(text)


# ── Main entry ──────────────────────────────────────────────────────────────


def semantic_search(
    db: Session,
    *,
    org_id: UUID,
    query: str,
    source: Literal["database", "outbound", "imported_csv", "all"] = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Return an anonymized shortlist for a natural-language query.

    Response shape:

      ``{
        query, source, limit,
        semantic_search_used: bool,      # False when we fell back to SQL
        agent_available: bool,           # False when every row used fallback
        results: [SemanticSearchResult.to_dict(), ...],
      }``
    """
    limit = max(1, min(int(limit or 10), 50))
    keywords = _query_keywords(query)

    # ── 1. Embed + Qdrant search ───────────────────────────────────────
    semantic_used = False
    qdrant_hits: list[tuple[str, float]] = []  # (candidate_id, cosine 0..1ish)
    try:
        q_vec = embed_query(query.strip() or "candidate")
        qdr = QdrantService()
        raw_hits = qdr.search_vectors(
            collection_name=settings.qdrant_candidate_collection,
            query_vector=q_vec,
            limit=min(limit * 4, 200),
        )
        for h in raw_hits:
            cid = h.get("id") or (h.get("payload") or {}).get("candidate_id")
            if cid:
                qdrant_hits.append((str(cid), float(h.get("score", 0.0))))
        semantic_used = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic_search: vector path failed (%s); using SQL fallback", exc)

    # ── 2. Load candidate rows + filter by org-visibility + source ──
    candidate_scores: list[tuple[Candidate, int]] = []  # (cand, score 0..100)
    seen: set[str] = set()

    if semantic_used and qdrant_hits:
        ids = []
        for cid, _ in qdrant_hits:
            try:
                ids.append(UUID(cid))
            except ValueError:
                continue
        if ids:
            rows = db.execute(
                select(Candidate).where(Candidate.id.in_(ids))
            ).scalars().all()
            by_id = {str(c.id): c for c in rows}
            for cid, cos in qdrant_hits:
                cand = by_id.get(cid)
                if cand is None or cid in seen:
                    continue
                seen.add(cid)
                if not _matches_source_filter(cand, source):
                    continue
                if not org_can_view_candidate(db, org_id, cand.id):
                    continue
                # Map cosine ~[-1..1] (sometimes [0..1] depending on metric) → 0..100
                if cos > 1.0:
                    cos_norm = min(1.0, cos / 100.0)
                elif cos < -0.0001:
                    cos_norm = (cos + 1.0) / 2.0
                else:
                    cos_norm = cos
                score = int(round(max(0.0, min(1.0, cos_norm)) * 100))
                candidate_scores.append((cand, score))
                if len(candidate_scores) >= limit:
                    break

    if not candidate_scores:
        # Fallback path — pure SQL keyword overlap.
        fb = _sql_fallback_rank(db, org_id=org_id, query_keywords=keywords, limit=limit * 2)
        for cand, score in fb:
            if not _matches_source_filter(cand, source):
                continue
            if not org_can_view_candidate(db, org_id, cand.id):
                continue
            candidate_scores.append((cand, score))
            if len(candidate_scores) >= limit:
                break

    if not candidate_scores:
        return {
            "query": query,
            "source": source,
            "limit": limit,
            "semantic_search_used": semantic_used,
            "agent_available": True,
            "results": [],
        }

    # ── 3. Per-row signal extraction + agent explanation ────────────
    results: list[SemanticSearchResult] = []
    agent_failures = 0
    for idx, (cand, semantic_score) in enumerate(candidate_scores[:limit], start=1):
        matched, missing = _split_matched_missing(cand, keywords)
        has_profile = bool(
            (cand.summary or "").strip()
            or (cand.skills or [])
            or (cand.current_title or "").strip()
        )
        confidence = _confidence(
            semantic_score=semantic_score,
            matched=len(matched),
            total=len(keywords),
            has_profile=has_profile,
        )
        alias = candidate_alias(cand.id, index=idx)
        evidence = anonymized_evidence_block(cand, alias=alias)

        explanation, used_fallback = _agent_explanation(
            query=query,
            evidence=evidence,
            matched=matched,
            missing=missing,
            semantic_score=semantic_score,
        )
        if used_fallback:
            agent_failures += 1
            if not explanation:
                explanation = (
                    "Agent explanation could not be generated. Please retry."
                )

        source_tag = derive_source(cand)
        results.append(
            SemanticSearchResult(
                candidate_id=str(cand.id),
                anonymized_label=alias,
                source=source_tag,
                source_display=source_display(source_tag),
                headline=(cand.headline or None),
                current_title=(cand.current_title or None),
                semantic_score=int(semantic_score),
                confidence=confidence,
                matched_evidence=matched[:8],
                missing_signals=missing[:8],
                agent_explanation=explanation,
            )
        )

    return {
        "query": query,
        "source": source,
        "limit": limit,
        "semantic_search_used": semantic_used,
        "agent_available": agent_failures < len(results),
        "results": [r.to_dict() for r in results],
    }


# Re-exported by __init__
__all__ = ["semantic_search", "SemanticSearchResult"]

# Silence unused-import lint for shared chunk type
_ = EvidenceChunk
