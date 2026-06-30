"""
Per-skill evidence orchestrator.

Public API:

  collect_skill_evidence(db, candidate_id, skill_name)
      → SkillEvidenceReport     # one skill, full per-source breakdown
  refresh_candidate_skill_evidence(db, candidate_id, skill_filter=None)
      → list[SkillEvidenceReport]
  load_persisted_evidence(db, candidate_id)
      → list[SkillEvidenceReport]

What the orchestrator does for each skill:

  1. Calls every MCP-style tool (``CVEvidenceTool``, ``GithubEvidenceTool``,
     ``LinkedinEvidenceTool``) in parallel-friendly order. Each tool
     returns a uniform ``EvidenceResult``.

  2. Hands each tool's snippets to the **LLM scorer** (OpenRouter free-
     model chain via ``generate_json_response``) and asks for a per-
     source 0..100 score + a one-line reasoning sentence.

  3. Computes the **aggregate score** as a normalised weighted average
     of the per-source scores from sources that actually had evidence —
     missing sources are excluded from the denominator instead of being
     counted as a 0. That matches the same "re-base the weights" trick
     the IDSS rubric uses so missing sources don't unfairly punish.

  4. Persists everything into ``evidence_items`` (one row per source) +
     updates ``candidate_skills.proficiency_score`` and
     ``candidate_skills.evidence_text``.

A defensive fallback computes a deterministic per-source score from the
snippet count when the LLM is unavailable (rate-limited / blank API
key). Better than letting the whole refresh fail.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateSkill, Skill
from app.db.models.evidence import CandidateSource, EvidenceItem
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)
from app.services.skill_evidence.cv_tool import CVEvidenceTool
from app.services.skill_evidence.github_tool import GithubEvidenceTool
# LinkedinEvidenceTool intentionally not used — Candidate.md §4 removed
# LinkedIn from the skill-scoring rubric (CV 50% + GitHub 50%).
from app.services.skill_evidence.types import EvidenceResult, EvidenceSnippet

logger = logging.getLogger(__name__)


_EVIDENCE_TYPE_PREFIX = "skill_evidence_"
_FIELD_REF_PREFIX = "skill:"


@dataclass
class SourceScore:
    source: str
    status: str
    score: int | None          # 0..100, None when no evidence
    reasoning: str
    snippets: list[dict[str, Any]] = field(default_factory=list)
    source_url: str | None = None
    weight: float = 0.0
    fallback: bool = False


@dataclass
class SkillEvidenceReport:
    skill: str
    aggregate_score: int          # 0..100
    confidence: str               # high | medium | low
    sources: list[SourceScore]
    last_refreshed_at: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "aggregate_score": self.aggregate_score,
            "confidence": self.confidence,
            "summary": self.summary,
            "last_refreshed_at": self.last_refreshed_at,
            "sources": [
                {
                    "source": s.source,
                    "status": s.status,
                    "score": s.score,
                    "reasoning": s.reasoning,
                    "snippets": s.snippets,
                    "source_url": s.source_url,
                    "weight": s.weight,
                    "fallback": s.fallback,
                }
                for s in self.sources
            ],
        }


# ── Public API ──────────────────────────────────────────────────────


def collect_skill_evidence(
    db: Session, *, candidate_id: uuid.UUID, skill: str,
) -> SkillEvidenceReport:
    """Collect evidence for a single skill on a single candidate."""
    weights = _resolve_weights()

    # Candidate.md §4 — scoring rubric is CV 50% + GitHub 50%. LinkedIn was
    # removed from the rubric (the tool still exists but no longer scores).
    tools = [
        ("cv", CVEvidenceTool(db)),
        ("github", GithubEvidenceTool(db)),
    ]

    per_source: list[SourceScore] = []
    for source_name, tool in tools:
        result = tool.gather_evidence(candidate_id=candidate_id, skill=skill)
        score_obj = _score_source(skill=skill, result=result, weight=weights.get(source_name, 0.0))
        per_source.append(score_obj)

    agg, confidence = _aggregate(per_source)
    summary = _build_summary(skill, per_source, agg)

    report = SkillEvidenceReport(
        skill=skill,
        aggregate_score=agg,
        confidence=confidence,
        sources=per_source,
        summary=summary,
    )

    _persist(db, candidate_id=candidate_id, report=report)
    return report


def refresh_candidate_skill_evidence(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    skill_filter: list[str] | None = None,
    max_skills: int = 25,
) -> list[SkillEvidenceReport]:
    """Refresh evidence for every skill on the candidate (or a filtered subset)."""
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")

    skills = _candidate_skill_list(db, candidate_id, cand)
    if skill_filter:
        wanted = {s.strip().lower() for s in skill_filter if s and s.strip()}
        skills = [s for s in skills if s.lower() in wanted]
    skills = skills[:max_skills]
    if not skills:
        return []

    reports: list[SkillEvidenceReport] = []
    for skill in skills:
        try:
            reports.append(
                collect_skill_evidence(db, candidate_id=candidate_id, skill=skill),
            )
        except Exception:  # noqa: BLE001 — one bad skill must not kill the rest
            logger.exception(
                "[SkillEvidence] failed to score skill %r for candidate %s",
                skill, candidate_id,
            )
    return reports


def load_persisted_evidence(
    db: Session, *, candidate_id: uuid.UUID,
) -> list[SkillEvidenceReport]:
    """Reassemble the latest persisted evidence into SkillEvidenceReport-s
    so the GET endpoint doesn't re-run the agent on every page load."""
    rows = list(
        db.execute(
            select(EvidenceItem)
            .where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.type.like(f"{_EVIDENCE_TYPE_PREFIX}%"),
            )
            .order_by(EvidenceItem.created_at.desc())
        ).scalars().all()
    )

    # Group by skill name.
    by_skill: dict[str, dict[str, EvidenceItem]] = {}
    for row in rows:
        if not row.field_ref or not row.field_ref.startswith(_FIELD_REF_PREFIX):
            continue
        skill = row.field_ref[len(_FIELD_REF_PREFIX):]
        source = row.type[len(_EVIDENCE_TYPE_PREFIX):]
        # Most-recent wins per (skill, source) — rows come in DESC order.
        by_skill.setdefault(skill, {}).setdefault(source, row)

    out: list[SkillEvidenceReport] = []
    weights = _resolve_weights()
    for skill, src_map in by_skill.items():
        per_source: list[SourceScore] = []
        latest_ts: str | None = None
        # Candidate.md §4 — only CV + GitHub feed the rubric now.
        for source in ("cv", "github"):
            row = src_map.get(source)
            if row is None:
                # Source never ran — emit a synthetic "url_missing" entry so
                # the UI always renders three rows.
                per_source.append(
                    SourceScore(
                        source=source,
                        status="not_run",
                        score=None,
                        reasoning="No evidence collected yet for this source.",
                        weight=weights.get(source, 0.0),
                    )
                )
                continue
            meta = row.meta_json or {}
            iso_ts = row.created_at.isoformat() if row.created_at else None
            if iso_ts and (latest_ts is None or iso_ts > latest_ts):
                latest_ts = iso_ts
            per_source.append(
                SourceScore(
                    source=source,
                    status=str(meta.get("status") or "available"),
                    score=meta.get("score"),
                    reasoning=str(meta.get("reasoning") or row.extracted_text or ""),
                    snippets=meta.get("snippets") or [],
                    source_url=row.source_uri,
                    weight=float(meta.get("weight") or weights.get(source, 0.0)),
                    fallback=bool(meta.get("fallback")),
                )
            )
        agg, conf = _aggregate(per_source)
        out.append(
            SkillEvidenceReport(
                skill=skill,
                aggregate_score=agg,
                confidence=conf,
                sources=per_source,
                summary=_build_summary(skill, per_source, agg),
                last_refreshed_at=latest_ts,
            )
        )
    out.sort(key=lambda r: r.aggregate_score, reverse=True)
    return out


# ── Internals ───────────────────────────────────────────────────────


def _candidate_skill_list(
    db: Session, candidate_id: uuid.UUID, cand: Candidate,
) -> list[str]:
    """Pull a deduped list of skills for this candidate.

    Reads from both the relational ``candidate_skills`` table (with
    skill names joined in) and the raw ``Candidate.skills`` array, so
    candidates ingested via either path are covered.
    """
    rows = list(
        db.execute(
            select(Skill.normalized_name)
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .where(CandidateSkill.candidate_id == candidate_id)
        ).all()
    )
    relational = [r[0] for r in rows if r[0]]
    raw = [s for s in (cand.skills or []) if isinstance(s, str) and s.strip()]

    seen: set[str] = set()
    out: list[str] = []
    for s in relational + raw:
        key = s.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s.strip())
    return out


def _resolve_weights() -> dict[str, float]:
    """Read the configured per-source weights, falling back to defaults.

    Candidate.md §4 — the rubric is CV 50% + GitHub 50%. LinkedIn is no
    longer part of the score, so it is ignored even if still present in the
    configured JSON.
    """
    settings = get_settings()
    default = {"cv": 50.0, "github": 50.0}
    blob = settings.skill_evidence_weights_json
    if not blob:
        return default
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        logger.warning("[SkillEvidence] SKILL_EVIDENCE_WEIGHTS_JSON not JSON; using defaults")
        return default
    if not isinstance(parsed, dict):
        return default
    cleaned = {
        k: float(v)
        for k, v in parsed.items()
        if k in default and isinstance(v, (int, float))  # linkedin dropped here
    }
    total = sum(cleaned.values())
    if total <= 0:
        return default
    if abs(total - 100.0) > 0.01:
        factor = 100.0 / total
        cleaned = {k: round(v * factor, 4) for k, v in cleaned.items()}
    # Make sure both sources have an entry, even if 0.
    for k in default:
        cleaned.setdefault(k, 0.0)
    return cleaned


def _score_source(
    *, skill: str, result: EvidenceResult, weight: float,
) -> SourceScore:
    """Turn a tool's raw evidence into a 0-100 score for that source."""
    snippets_serialised = _serialise_snippets(result.snippets)
    # Pull a representative source URL — first non-null in snippet list.
    source_url = next(
        (s.source_url for s in result.snippets if s.source_url), None,
    )

    if result.status != "available" or not result.snippets:
        return SourceScore(
            source=result.source,
            status=result.status,
            score=None,
            reasoning=result.reason or "No evidence available from this source.",
            snippets=snippets_serialised,
            source_url=source_url,
            weight=weight,
        )

    # ── LLM scorer ─────────────────────────────────────────────────
    system = (
        "You are an evidence-scoring agent. Given a skill and the "
        "candidate's evidence from ONE source, return a JSON object: "
        '{"score": <0..100>, "reasoning": "<one sentence>"}. '
        "Use the 0-100 scale strictly: 0 means no real evidence, 50 means "
        "passing mention, 70 means concrete project/task, 85 means deep "
        "applied use, 95+ means proven mastery with measurable output. "
        "Never invent details that aren't in the snippets."
    )
    user_payload = {
        "skill": skill,
        "source": result.source,
        "evidence_snippets": [s["text"] for s in snippets_serialised][:10],
        "tool_metadata": result.raw or {},
    }
    try:
        raw = generate_json_response(
            system,
            json.dumps(user_payload, default=str)[:11000],
            temperature=0.1,
            max_tokens=300,
        )
    except OpenRouterClientError as exc:
        logger.warning("[SkillEvidence] LLM unavailable for %s/%s — using fallback", skill, result.source)
        return SourceScore(
            source=result.source,
            status="available",
            score=_fallback_score(result),
            reasoning=(
                f"Fallback heuristic ({len(result.snippets)} matching "
                f"snippet(s)). LLM unavailable: {exc!s:.120}."
            ),
            snippets=snippets_serialised,
            source_url=source_url,
            weight=weight,
            fallback=True,
        )

    try:
        score = int(round(float(raw.get("score"))))
    except (TypeError, ValueError):
        score = _fallback_score(result)
    score = max(0, min(100, score))
    reasoning = str(raw.get("reasoning") or "").strip()
    if not reasoning:
        reasoning = (
            f"Agent assigned {score}/100 from "
            f"{len(result.snippets)} {result.source} snippet(s)."
        )

    return SourceScore(
        source=result.source,
        status="available",
        score=score,
        reasoning=reasoning,
        snippets=snippets_serialised,
        source_url=source_url,
        weight=weight,
    )


def _fallback_score(result: EvidenceResult) -> int:
    """Deterministic score used when the LLM is unavailable.

    Linear ramp on snippet count: 1 snippet = 35, 2 = 50, 3 = 60, 4 = 70,
    5+ = 80. Plus a small bump when any snippet has weight_hint > 1
    (e.g. README excerpts / starred repos).
    """
    n = len(result.snippets)
    if n == 0:
        return 0
    base = {1: 35, 2: 50, 3: 60, 4: 70}.get(n, 80)
    if any((s.weight_hint or 1.0) > 1.0 for s in result.snippets):
        base = min(100, base + 5)
    return base


def _aggregate(per_source: list[SourceScore]) -> tuple[int, str]:
    """Final skill score = CV (0-50) + GitHub (0-50), clamped 0-100.

    Candidate.md §4/§5 — each source contributes up to its weight (50 each),
    and a missing source counts as 0 for its half rather than being excluded.
    With 50/50 weights and per-source 0-100 scores this is exactly
    ``round(cv*0.5 + github*0.5)``. The source weight still counts in the
    denominator so a missing GitHub caps the score at the CV half.
    """
    total_weight = 0.0
    weighted_sum = 0.0
    contributing = 0
    for src in per_source:
        total_weight += src.weight          # weight counts even when missing
        if src.score is not None:
            weighted_sum += src.score * src.weight
            contributing += 1
    if total_weight <= 0:
        return 0, "low"
    agg = round(weighted_sum / total_weight)
    agg = max(0, min(100, agg))
    # Two-source rubric: both present = high, one = medium, none = low.
    confidence = "high" if contributing >= 2 else "medium" if contributing == 1 else "low"
    return agg, confidence


def _build_summary(skill: str, per_source: list[SourceScore], agg: int) -> str:
    parts = []
    for src in per_source:
        label = src.source.upper()
        if src.score is None:
            parts.append(f"{label}: {src.status}")
        else:
            parts.append(f"{label}: {src.score}/100")
    return f"{skill} → {agg}/100 ({', '.join(parts)})"


def _serialise_snippets(snippets: list[EvidenceSnippet]) -> list[dict[str, Any]]:
    return [
        {
            "text": s.text,
            "source_url": s.source_url,
            "weight_hint": s.weight_hint,
            "metadata": s.metadata or {},
        }
        for s in (snippets or [])
        if s and s.text
    ]


def _persist(
    db: Session, *, candidate_id: uuid.UUID, report: SkillEvidenceReport,
) -> None:
    field_ref = f"{_FIELD_REF_PREFIX}{report.skill.strip().lower()}"

    # Wipe the prior evidence_items for this (candidate, skill) tuple so
    # each refresh produces a clean snapshot rather than appending forever.
    db.execute(
        delete(EvidenceItem).where(
            EvidenceItem.candidate_id == candidate_id,
            EvidenceItem.field_ref == field_ref,
            EvidenceItem.type.like(f"{_EVIDENCE_TYPE_PREFIX}%"),
        )
    )

    for src in report.sources:
        meta: dict[str, Any] = {
            "score": src.score,
            "status": src.status,
            "reasoning": src.reasoning,
            "snippets": src.snippets,
            "weight": src.weight,
            "fallback": src.fallback,
            "aggregate_score": report.aggregate_score,
            "confidence": report.confidence,
        }
        # Confidence: rough 0..1 derived from the score so existing
        # consumers of `EvidenceItem.confidence` (which is a float) still
        # work without bespoke logic.
        item = EvidenceItem(
            candidate_id=candidate_id,
            ingestion_job_id=f"skill_evidence:{report.skill[:32]}",
            type=f"{_EVIDENCE_TYPE_PREFIX}{src.source}",
            field_ref=field_ref,
            source_uri=src.source_url,
            extracted_text=src.reasoning[:2000] if src.reasoning else None,
            confidence=(src.score / 100.0) if src.score is not None else None,
            meta_json=meta,
        )
        db.add(item)

    # Update the relational CandidateSkill row (or create one) with the
    # aggregate so existing scoring code that reads
    # ``CandidateSkill.proficiency_score`` picks up the new number.
    _upsert_candidate_skill(db, candidate_id=candidate_id, report=report)

    db.commit()


def _upsert_candidate_skill(
    db: Session, *, candidate_id: uuid.UUID, report: SkillEvidenceReport,
) -> None:
    skill_name = report.skill.strip()
    if not skill_name:
        return
    normalised = skill_name.lower()
    skill_row = db.execute(
        select(Skill).where(Skill.normalized_name == normalised).limit(1)
    ).scalar_one_or_none()
    if skill_row is None:
        skill_row = Skill(normalized_name=normalised)
        db.add(skill_row)
        db.flush()

    cs = db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id,
            CandidateSkill.skill_id == skill_row.id,
        ).limit(1)
    ).scalar_one_or_none()

    summary_text = report.summary[:2000] if report.summary else None
    if cs is None:
        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                skill_id=skill_row.id,
                proficiency_score=report.aggregate_score,
                evidence_text=summary_text,
            )
        )
    else:
        cs.proficiency_score = report.aggregate_score
        cs.evidence_text = summary_text


# ── Profile URL maintenance ─────────────────────────────────────────


def upsert_profile_url(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    source: str,
    url: str | None,
) -> None:
    """Set or clear the candidate's LinkedIn / GitHub URL.

    Re-uses the existing ``candidate_sources`` table — the same table the
    sourcing flow already writes to — so there's no new schema.
    """
    if source not in {"github", "linkedin", "portfolio"}:
        raise ValueError(f"unsupported source: {source}")
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")

    row = db.execute(
        select(CandidateSource).where(
            CandidateSource.candidate_id == candidate_id,
            CandidateSource.source == source,
        ).limit(1)
    ).scalar_one_or_none()

    cleaned = (url or "").strip() or None
    if row is None:
        if cleaned is None:
            return
        db.add(
            CandidateSource(
                candidate_id=candidate_id,
                source=source,
                url=cleaned,
            )
        )
    else:
        row.url = cleaned
    db.commit()


def list_profile_urls(
    db: Session, *, candidate_id: uuid.UUID,
) -> dict[str, str | None]:
    rows = list(
        db.execute(
            select(CandidateSource).where(
                CandidateSource.candidate_id == candidate_id,
                CandidateSource.source.in_(("github", "linkedin", "portfolio")),
            )
        ).scalars().all()
    )
    out: dict[str, str | None] = {"github": None, "linkedin": None, "portfolio": None}
    for r in rows:
        out[r.source] = r.url
    return out


__all__ = [
    "SkillEvidenceReport",
    "SourceScore",
    "collect_skill_evidence",
    "list_profile_urls",
    "load_persisted_evidence",
    "refresh_candidate_skill_evidence",
    "upsert_profile_url",
]
