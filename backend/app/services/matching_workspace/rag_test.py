"""RAG-grounded candidate-vs-requirement test (fix7.md "Direct Test").

For each (candidate, requirement) pair we:

  1. Build small evidence chunks from the candidate's structured profile
     (summary, headline, skills, experiences, education).
  2. Embed each chunk + the requirement, retrieve the top-K chunks by
     cosine similarity. This is in-process retrieval (no Qdrant chunk
     collection yet); the call still degrades gracefully if Ollama is
     unreachable — we fall back to keyword overlap ranking.
  3. Pass the retrieved chunks + structured profile + requirement to
     OpenRouter with a strict rubric schema.
  4. Return a deterministic numeric result even when the LLM is down —
     the rubric is computed from the retrieved signals so HR still gets
     a usable score.

This is intentionally lightweight: no persisted runs (the spec calls
them out as optional), and the response shape matches fix7 §3 ("Direct
Test Output") exactly.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.candidate_access import org_can_view_candidate
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.services.embedding_service import embed_documents, embed_query

from .common import (
    EvidenceChunk,
    anonymized_evidence_block,
    build_evidence_chunks,
    candidate_alias,
    scrub_pii,
)

logger = logging.getLogger(__name__)


# ── Public types ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RagTestResult:
    candidate_id: str
    anonymized_label: str
    job_title: str | None
    requirement_label: str
    final_score: int
    confidence: int
    next_action: str
    rubric: dict[str, int]
    agent_explanation: str
    candidate_evidence_used: list[dict[str, Any]]
    requirement_evidence_used: list[str]
    missing_data: list[str]
    used_agent_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "anonymized_label": self.anonymized_label,
            "job_title": self.job_title,
            "requirement_label": self.requirement_label,
            "final_score": self.final_score,
            "confidence": self.confidence,
            "next_action": self.next_action,
            "rubric": dict(self.rubric),
            "agent_explanation": self.agent_explanation,
            "candidate_evidence_used": list(self.candidate_evidence_used),
            "requirement_evidence_used": list(self.requirement_evidence_used),
            "missing_data": list(self.missing_data),
            "used_agent_fallback": self.used_agent_fallback,
        }


# ── Requirement construction ────────────────────────────────────────────────


def _job_requirement_text(job: Job) -> str:
    parts: list[str] = []
    if job.title:
        parts.append(f"Title: {job.title}")
    if job.seniority_level:
        parts.append(f"Seniority: {job.seniority_level}")
    if job.summary:
        parts.append(f"Summary: {job.summary}")
    if job.description_text:
        parts.append(f"Description: {job.description_text}")
    if job.requirements:
        parts.append(f"Requirements: {job.requirements}")
    return "\n".join(parts)[:6000]


_REQ_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,30}")


def _extract_requirement_signals(text: str) -> list[str]:
    """Pull out distinct, non-stopword tokens to use as the requirement spine."""
    seen: set[str] = set()
    out: list[str] = []
    skip = {
        "a", "an", "and", "the", "with", "for", "of", "in", "on", "at", "by",
        "or", "to", "from", "as", "is", "are", "be", "was", "were", "we",
        "must", "have", "has", "had", "should", "would", "could",
        "experience", "years", "year", "plus", "engineer", "engineers",
        "developer", "developers", "role", "team",
    }
    for m in _REQ_TOKEN_RE.finditer(text or ""):
        tok = m.group(0)
        norm = tok.lower()
        if norm in skip or norm in seen:
            continue
        seen.add(norm)
        out.append(tok)
    return out[:30]


# ── Vector retrieval (in-process) ───────────────────────────────────────────


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def _retrieve_top_chunks(
    requirement_text: str,
    chunks: list[EvidenceChunk],
    *,
    top_k: int = 5,
) -> list[EvidenceChunk]:
    """Return the top-K chunks ranked by cosine similarity to the requirement.

    Uses Ollama embeddings. On any failure (model down, dim mismatch) we
    fall back to keyword-overlap scoring so the test still produces a
    plausible "retrieved evidence" set.
    """
    if not chunks:
        return []
    texts = [c.text for c in chunks]

    try:
        chunk_vecs = embed_documents(texts)
        if not chunk_vecs:
            raise RuntimeError("empty chunk_vecs")
        q_vec = embed_query(requirement_text or "candidate match")
        scored: list[tuple[EvidenceChunk, float]] = []
        for chunk, vec in zip(chunks, chunk_vecs):
            cos = _cosine(q_vec, vec)
            scored.append((chunk, max(0.0, (cos + 1.0) / 2.0)))
        scored.sort(key=lambda r: r[1], reverse=True)
        out: list[EvidenceChunk] = []
        for chunk, score in scored[:top_k]:
            out.append(
                EvidenceChunk(
                    field=chunk.field,
                    text=chunk.text,
                    source_label=chunk.source_label,
                    score=round(score, 4),
                )
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "rag_test: vector retrieval unavailable (%s) — keyword fallback", exc,
        )

    # Keyword overlap fallback
    req_tokens = {t.lower() for t in _extract_requirement_signals(requirement_text)}
    scored_kw: list[tuple[EvidenceChunk, float]] = []
    for c in chunks:
        toks = {t.lower() for t in _REQ_TOKEN_RE.findall(c.text)}
        if not toks or not req_tokens:
            scored_kw.append((c, 0.0))
            continue
        overlap = len(toks & req_tokens) / max(1, len(req_tokens))
        scored_kw.append((c, overlap))
    scored_kw.sort(key=lambda r: r[1], reverse=True)
    return [
        EvidenceChunk(
            field=c.field, text=c.text, source_label=c.source_label, score=round(s, 4),
        )
        for c, s in scored_kw[:top_k]
    ]


# ── Rubric / score computation ──────────────────────────────────────────────


def _normalize_pct(v: int) -> int:
    return max(0, min(100, int(round(v))))


def _baseline_rubric(
    cand: Candidate,
    requirement_tokens: list[str],
    retrieved_chunks: list[EvidenceChunk],
) -> dict[str, int]:
    """Compute a deterministic rubric so we always have numeric grounding.

    Each criterion is scored 0..100 from the structured evidence the
    profile actually has; the LLM may later refine these numbers.

    Spec keys (fix7 §3): technical_fit, experience_fit, skill_evidence,
    project_portfolio_evidence, missing_requirements, risk_factors.
    """
    skills_lower = {str(s).lower() for s in (cand.skills or [])}
    title_lower = (cand.current_title or "").lower()
    head_summary_lower = " ".join(filter(None, [cand.headline, cand.summary])).lower()
    req_lower = {t.lower() for t in requirement_tokens}

    skill_hits = len(req_lower & skills_lower)
    title_hits = sum(1 for t in req_lower if t in title_lower)
    text_hits = sum(1 for t in req_lower if t in head_summary_lower)

    if not req_lower:
        skill_evidence = 50
        technical_fit = 50
        missing_score = 50
    else:
        skill_evidence = _normalize_pct(100 * skill_hits / max(1, len(req_lower)))
        technical_fit = _normalize_pct(
            (skill_evidence + min(100, (title_hits + text_hits) * 25)) // 2
        )
        missing_score = _normalize_pct(
            100 * (len(req_lower) - skill_hits - title_hits) / max(1, len(req_lower))
        )

    yrs = cand.years_experience or 0
    experience_fit = _normalize_pct(min(100, yrs * 12))  # 8.3yrs → 100

    # Portfolio evidence — count meaningful retrieved chunks
    portfolio_evidence = _normalize_pct(min(100, 25 * len(retrieved_chunks)))

    risk = 0
    if not (cand.summary or "").strip():
        risk += 25
    if not skills_lower:
        risk += 35
    if yrs == 0:
        risk += 25
    risk = _normalize_pct(risk)

    return {
        "technical_fit": technical_fit,
        "experience_fit": experience_fit,
        "skill_evidence": skill_evidence,
        "project_portfolio_evidence": portfolio_evidence,
        "missing_requirements": missing_score,
        "risk_factors": risk,
    }


def _weighted_final_score(rubric: dict[str, int]) -> int:
    """Hybrid weighted score from the rubric (fix7 §5)."""
    val = (
        0.35 * rubric.get("technical_fit", 0)
        + 0.30 * rubric.get("skill_evidence", 0)
        + 0.20 * rubric.get("experience_fit", 0)
        + 0.10 * rubric.get("project_portfolio_evidence", 0)
        - 0.05 * rubric.get("missing_requirements", 0)
        - 0.05 * rubric.get("risk_factors", 0)
    )
    return _normalize_pct(val)


def _next_action(final_score: int, confidence: int) -> str:
    if final_score >= 75 and confidence >= 70:
        return "Strong shortlist"
    if final_score >= 60:
        return "Shortlist with concerns"
    if final_score >= 40:
        return "Needs manual review"
    return "Not recommended"


def _confidence(
    rubric: dict[str, int],
    chunks: list[EvidenceChunk],
    cand: Candidate,
) -> int:
    """Confidence reflects how solid the evidence is, not the score itself."""
    base = (
        rubric.get("skill_evidence", 0)
        + rubric.get("technical_fit", 0)
        + rubric.get("project_portfolio_evidence", 0)
    ) / 3
    if not chunks:
        base *= 0.5
    if not (cand.summary or "").strip():
        base *= 0.8
    base -= 0.4 * rubric.get("risk_factors", 0)
    return _normalize_pct(base)


# ── Agent prompt ────────────────────────────────────────────────────────────


_AGENT_SYSTEM = (
    "You are the PATHS RAG Test Agent.\n\n"
    "You evaluate, in HR-friendly language, how well an anonymized "
    "candidate matches a job or custom requirement based on retrieved "
    "evidence chunks.\n\n"
    "Rules:\n"
    "  • Do NOT reveal or infer the candidate's real identity.\n"
    "  • Do NOT mention protected attributes.\n"
    "  • Use ONLY the provided evidence — never invent skills, "
    "employers, degrees, or experience.\n"
    "  • Be concise and recruiter-friendly (3-5 sentences).\n"
    "  • Highlight both strengths AND missing evidence.\n"
    '  • Output ONLY a single JSON object: {"agentExplanation":"<text>"}.'
)


def _agent_explanation(
    *,
    requirement_text: str,
    requirement_label: str,
    evidence: dict[str, Any],
    rubric: dict[str, int],
    final_score: int,
    next_action: str,
) -> tuple[str, bool]:
    try:
        from app.services.llm.openrouter_client import (
            OpenRouterClientError,
            generate_json_response,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("openrouter import failed: %s", exc)
        return "", True

    user = (
        f"Requirement label: {requirement_label}\n"
        f"Requirement text:\n{requirement_text[:4000]}\n\n"
        f"Anonymized candidate evidence (JSON):\n{evidence}\n\n"
        f"Computed rubric (0-100 each): {rubric}\n"
        f"Computed final score (0-100): {final_score}\n"
        f"Suggested next action: {next_action}\n\n"
        'Return JSON only: {"agentExplanation":"<3-5 sentences mentioning '
        'strengths, gaps, and what HR should do next>"}.'
    )
    try:
        raw = generate_json_response(_AGENT_SYSTEM, user, temperature=0.2, max_tokens=400)
    except OpenRouterClientError as exc:
        logger.info("rag_test agent unavailable: %s", str(exc)[:120])
        return "", True
    except Exception as exc:  # noqa: BLE001
        logger.warning("rag_test agent failed: %s", exc)
        return "", True

    if not isinstance(raw, dict):
        return "", True
    text = scrub_pii(str(raw.get("agentExplanation") or "").strip())
    return text, not bool(text)


# ── Public entry ────────────────────────────────────────────────────────────


def run_rag_test(
    db: Session,
    *,
    org_id: UUID,
    candidate_ids: list[UUID],
    job_id: UUID | None = None,
    custom_requirements: str | None = None,
    top_k_chunks: int = 5,
) -> dict[str, Any]:
    """Test multiple candidates against a job OR custom requirement text.

    Exactly one of ``job_id`` / ``custom_requirements`` must be provided.
    Returns ``{tests: [...], agent_available, retrieval_used}``.
    """
    if not candidate_ids:
        raise ValueError("candidate_ids_required")
    if (job_id is None) == (custom_requirements is None):
        raise ValueError("provide_exactly_one_of_job_id_or_custom_requirements")

    job: Job | None = None
    requirement_label: str
    if job_id is not None:
        job = db.get(Job, job_id)
        if job is None:
            raise ValueError("job_not_found")
        requirement_text = _job_requirement_text(job)
        requirement_label = job.title or "Existing job"
    else:
        requirement_text = (custom_requirements or "").strip()
        if not requirement_text:
            raise ValueError("custom_requirements_empty")
        requirement_label = "Custom requirements"

    requirement_tokens = _extract_requirement_signals(requirement_text)

    tests: list[RagTestResult] = []
    agent_failures = 0
    retrieval_used = False

    for idx, cid in enumerate(candidate_ids[:25], start=1):
        if not org_can_view_candidate(db, org_id, cid):
            continue
        cand = db.get(Candidate, cid)
        if cand is None:
            continue

        chunks = build_evidence_chunks(db, cid)
        retrieved = _retrieve_top_chunks(
            requirement_text, chunks, top_k=max(1, min(int(top_k_chunks or 5), 10)),
        )
        if retrieved and any(c.score > 0 for c in retrieved):
            retrieval_used = True

        rubric = _baseline_rubric(cand, requirement_tokens, retrieved)
        final_score = _weighted_final_score(rubric)
        confidence = _confidence(rubric, retrieved, cand)
        next_action = _next_action(final_score, confidence)

        alias = candidate_alias(cand.id, index=idx)
        evidence_block = anonymized_evidence_block(
            cand, alias=alias, extra_chunks=retrieved,
        )

        explanation, used_fallback = _agent_explanation(
            requirement_text=requirement_text,
            requirement_label=requirement_label,
            evidence=evidence_block,
            rubric=rubric,
            final_score=final_score,
            next_action=next_action,
        )
        if used_fallback:
            agent_failures += 1
            if not explanation:
                explanation = (
                    "Agent explanation could not be generated. Please retry. "
                    f"Numeric score is based on structured evidence: rubric "
                    f"{rubric}."
                )

        # Missing-data flags surface gaps in the profile.
        missing: list[str] = []
        if not (cand.summary or "").strip():
            missing.append("No CV summary on file")
        if not cand.skills:
            missing.append("No skills listed")
        if cand.years_experience is None:
            missing.append("Years of experience missing")
        if not chunks:
            missing.append("Profile contains no evidence chunks")

        tests.append(
            RagTestResult(
                candidate_id=str(cand.id),
                anonymized_label=alias,
                job_title=job.title if job else None,
                requirement_label=requirement_label,
                final_score=final_score,
                confidence=confidence,
                next_action=next_action,
                rubric=rubric,
                agent_explanation=explanation,
                candidate_evidence_used=[
                    {
                        "field": c.field,
                        "label": c.source_label,
                        "excerpt": c.text[:500],
                        "relevance": c.score,
                    }
                    for c in retrieved
                ],
                requirement_evidence_used=requirement_tokens[:20],
                missing_data=missing,
                used_agent_fallback=used_fallback,
            )
        )

    return {
        "tests": [t.to_dict() for t in tests],
        "agent_available": agent_failures < max(1, len(tests)),
        "retrieval_used": retrieval_used,
        "requirement_label": requirement_label,
        "job_title": job.title if job else None,
    }


__all__ = ["run_rag_test", "RagTestResult"]
