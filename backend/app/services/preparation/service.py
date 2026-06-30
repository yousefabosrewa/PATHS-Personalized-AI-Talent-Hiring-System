"""
PATHS Preparation Agent — backend service (fix3.md §5–§6).

Single entry point: :pyfunc:`generate_preparation`.  Given a candidate id,
optional job id, and an output type, it builds an *anonymized* context and
calls the existing OpenRouter LLM chain to produce structured JSON.

Every output type returns a strict schema so the frontend can render it
without ad-hoc parsing.
"""

from __future__ import annotations

import logging
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
from app.db.models.job import Job
from app.db.models.preparation import PreparationDraft
from app.services.llm.openrouter_client import generate_json_response

logger = logging.getLogger(__name__)

PreparationOutputType = Literal[
    "pre_analysis",
    "technical_questions",
    "hr_questions",
    "assessment",
]


# ── Anonymized context builder ──────────────────────────────────────────────


def _candidate_alias(candidate_id: UUID | str) -> str:
    """Deterministic alias used in agent prompts + UI."""
    return f"Candidate {str(candidate_id).replace('-', '').upper()[:6]}"


def build_anonymized_context(
    db: Session,
    *,
    candidate_id: UUID,
    job_id: UUID | None = None,
) -> dict[str, Any]:
    """Build the strictly anonymized agent input (fix3.md §6 / §8.8).

    Never includes name, email, phone, photo, linkedin, github, or any
    direct identifier.  The agent must use the alias + structured evidence.
    """
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")

    # CandidateSkill.skill is a relationship to the Skill row, not a string —
    # the human-readable name lives on Skill.normalized_name.
    skills: list[str] = []
    for s in db.execute(
        select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)
    ).scalars().all():
        name = (getattr(s.skill, "normalized_name", None) or "").strip() if s.skill else ""
        if name:
            skills.append(name)
    experiences = [
        {
            "title":       (e.title or "").strip(),
            "description": (e.description or "").strip()[:600],
            "start_date":  str(e.start_date or "")[:10] or None,
            "end_date":    str(e.end_date or "")[:10] or None,
        }
        for e in db.execute(
            select(CandidateExperience)
            .where(CandidateExperience.candidate_id == candidate_id)
            .order_by(CandidateExperience.start_date.desc())
        ).scalars().all()[:6]
    ]
    educations = [
        {
            "degree":       (ed.degree or "").strip(),
            "field":        (ed.field_of_study or "").strip(),
            "institution":  "",  # institution name can leak identity if rare; omit
        }
        for ed in db.execute(
            select(CandidateEducation)
            .where(CandidateEducation.candidate_id == candidate_id)
        ).scalars().all()[:4]
    ]
    summary = (getattr(cand, "summary", "") or "").strip()[:1500]

    job_block: dict[str, Any] = {}
    if job_id is not None:
        job = db.get(Job, job_id)
        if job is not None:
            job_block = {
                "title":            getattr(job, "title", "") or "",
                "seniority_level":  getattr(job, "seniority_level", "") or "",
                "summary":          (getattr(job, "summary", "") or "")[:600],
                "requirements":     (getattr(job, "requirements", "") or "")[:1500],
                "description":      (getattr(job, "description_text", "") or "")[:1500],
            }

    return {
        "candidate_alias": _candidate_alias(candidate_id),
        "candidate_profile": {
            "skills": skills,
            "experience": experiences,
            "education": educations,
            "cv_summary": summary,
        },
        "job": job_block,
    }


# ── Schemas (compact docstrings the agent sees verbatim) ────────────────────


_SCHEMAS: dict[PreparationOutputType, str] = {
    "pre_analysis": """{
  "summary": "<2-3 sentences, no name>",
  "strengths": ["<bullet>", ...],
  "possible_gaps": ["<bullet>", ...],
  "risk_flags": ["<bullet>", ...],
  "recommended_focus_areas": ["<bullet>", ...],
  "interview_strategy": ["<bullet>", ...]
}""",
    "technical_questions": """{
  "questions": [
    {
      "question": "<concrete role-specific question>",
      "why_ask": "<one sentence>",
      "strong_answer_signals": ["<bullet>", ...],
      "weak_answer_signals":   ["<bullet>", ...],
      "rubric":               ["<criterion>", ...]
    }, ...
  ]
}""",
    "hr_questions": """{
  "questions": [
    {
      "question":   "<behavioural question>",
      "competency": "<motivation|teamwork|communication|ownership|problem_solving|culture_fit>",
      "why_ask":    "<one sentence>",
      "strong_answer_signals": ["<bullet>", ...],
      "red_flags":             ["<bullet>", ...]
    }, ...
  ]
}""",
    "assessment": """{
  "title": "<short>",
  "objective": "<one sentence>",
  "instructions": ["<step>", ...],
  "expected_deliverables": ["<deliverable>", ...],
  "time_estimate": "<e.g. 90 minutes>",
  "evaluation_rubric": ["<criterion>", ...]
}""",
}


_TYPE_INSTRUCTIONS: dict[PreparationOutputType, str] = {
    "pre_analysis":
        "Produce a recruiter-facing pre-analysis: identify strengths backed "
        "by evidence, possible gaps relative to the job, risk flags, focus "
        "areas, and an interview strategy.  Never restate the candidate's "
        "identity.  Treat missing data as missing evidence, not as weakness.",
    "technical_questions":
        "Generate 5 technical interview questions for THIS candidate applying "
        "to THIS job. Ground every question in the provided job requirements "
        "AND the candidate's own skills/experience evidence — each question's "
        "'why_ask' must name the specific job requirement and/or candidate "
        "skill it probes. Prefer real-world architecture, system-design, "
        "debugging and trade-off questions over leetcode trivia. Each question "
        "needs a rubric and strong/weak answer signals.",
    "hr_questions":
        "Generate 5 HR / behavioural interview questions for this candidate "
        "and job. Make them scenario / situational ('What would you do if…', "
        "'Tell me about a time when…') and tie them to the company culture "
        "and the role's context. Cover these competencies across the set: "
        "motivation, teamwork, communication, ownership, problem solving, and "
        "culture fit (set each question's 'competency' field accordingly). "
        "If company knowledge (culture/values/policies) is provided below, "
        "ground the culture-fit and scenario questions in it and reference "
        "those real company expectations rather than generic ones. "
        "Never ask about protected characteristics — age, family, religion, "
        "marital status, race, gender, or nationality. Include strong-answer "
        "signals and red flags for each.",
    "assessment":
        "Draft a single practical assessment task the candidate could "
        "complete asynchronously.  Make it role-specific, time-boxed, and "
        "evaluable from artifacts alone.  Provide clear instructions, "
        "expected deliverables, a time estimate, and an evaluation rubric.",
}


# ── Main entry point ────────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are the PATHS Preparation Agent.  Your role is to help a recruiter "
    "prepare for a structured, fair, evidence-based interview.\n\n"
    "Rules:\n"
    "  • Do not infer protected characteristics (race, gender, age, religion, "
    "marital status, disability, national origin, etc.).\n"
    "  • Do not ask illegal or biased questions.\n"
    "  • Do not use or invent a candidate name or personal identity.\n"
    "  • Focus on job-related evidence the candidate has provided.\n"
    "  • Highlight missing evidence as missing evidence, not as weakness.\n"
    "  • Output ONLY a single JSON object matching the requested schema; no "
    "Markdown, no preamble, no trailing prose.\n"
)


def generate_preparation(
    db: Session,
    *,
    candidate_id: UUID,
    output_type: PreparationOutputType,
    job_id: UUID | None = None,
    organization_id: UUID | None = None,
) -> dict[str, Any]:
    """Run the agent for one of the four output types.  Returns the parsed
    JSON dict (caller is responsible for persisting / returning to the UI).

    When ``organization_id`` is provided, HR / behavioural and pre-analysis
    runs are grounded in the organisation's Knowledge Base company files
    (culture, values, policies) so culture-fit questions reflect the real
    company context.
    """
    if output_type not in _SCHEMAS:
        raise ValueError(f"unknown output_type: {output_type}")

    try:
        ctx = build_anonymized_context(
            db, candidate_id=candidate_id, job_id=job_id,
        )
    except ValueError:
        # candidate_not_found etc. — let the caller turn this into a 4xx.
        raise
    except Exception as exc:  # noqa: BLE001
        # Any other context-building failure must not surface as an opaque
        # 500 (which the browser reports as "Failed to fetch" because the
        # error response carries no CORS headers). Fall back gracefully.
        logger.exception("[PreparationAgent] context build failed for %s", output_type)
        return _deterministic_fallback(
            output_type,
            {"candidate_alias": _candidate_alias(candidate_id), "job": {}},
            error=f"context_error: {exc}",
        )

    # Pull company Knowledge Base context for culture-aware outputs.
    company_context = ""
    if organization_id is not None and output_type in ("hr_questions", "pre_analysis"):
        company_context = _company_knowledge_context(organization_id, output_type)

    company_block = (
        f"Company knowledge (culture, values, policies — use to ground "
        f"culture-fit and scenario questions):\n{company_context}\n\n"
        if company_context
        else ""
    )

    user_prompt = (
        f"Output type: {output_type}\n\n"
        f"{_TYPE_INSTRUCTIONS[output_type]}\n\n"
        f"Candidate alias: {ctx['candidate_alias']}\n\n"
        f"Candidate evidence (JSON):\n{ctx['candidate_profile']}\n\n"
        f"Job context (JSON):\n{ctx['job']}\n\n"
        f"{company_block}"
        "Return ONLY a JSON object matching this schema:\n"
        f"{_SCHEMAS[output_type]}\n"
    )

    try:
        payload = generate_json_response(
            _SYSTEM_PROMPT,
            user_prompt,
            temperature=0.2,
            max_tokens=2400,
        )
        if not isinstance(payload, dict):
            raise ValueError("agent returned non-object")
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.exception("[PreparationAgent] generation failed for %s", output_type)
        # Deterministic fallback so the page never crashes (fix3.md §6 fallback).
        return _deterministic_fallback(output_type, ctx, error=str(exc))


def save_preparation_draft(
    db: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    job_id: UUID | None,
    output_type: str,
    content: dict[str, Any],
    user_id: UUID | None = None,
) -> PreparationDraft:
    """Upsert a draft for (org, candidate, job, type). Regeneration overwrites
    the existing row in place so the latest draft is what persists."""
    row = db.execute(
        select(PreparationDraft).where(
            PreparationDraft.organization_id == organization_id,
            PreparationDraft.candidate_id == candidate_id,
            PreparationDraft.job_id == job_id,  # SQLAlchemy maps None → IS NULL
            PreparationDraft.output_type == output_type,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PreparationDraft(
            organization_id=organization_id,
            candidate_id=candidate_id,
            job_id=job_id,
            output_type=output_type,
            content=content,
            generated_by_user_id=user_id,
        )
        db.add(row)
    else:
        row.content = content
        if user_id is not None:
            row.generated_by_user_id = user_id
    return row


def get_preparation_drafts(
    db: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    job_id: UUID | None = None,
) -> dict[str, dict[str, Any]]:
    """Return the latest saved draft per output_type for this candidate in the
    org. When ``job_id`` is given, job-specific drafts and candidate-wide
    (job-less) drafts are both considered, preferring the most recently updated.
    Shape: ``{output_type: {content, updated_at, job_id}}``."""
    stmt = select(PreparationDraft).where(
        PreparationDraft.organization_id == organization_id,
        PreparationDraft.candidate_id == candidate_id,
    )
    if job_id is not None:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(PreparationDraft.job_id == job_id, PreparationDraft.job_id.is_(None))
        )
    stmt = stmt.order_by(PreparationDraft.updated_at.desc())
    out: dict[str, dict[str, Any]] = {}
    for row in db.execute(stmt).scalars().all():
        if row.output_type in out:
            continue  # keep the most recent (rows are desc by updated_at)
        out[row.output_type] = {
            "content": row.content,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "job_id": str(row.job_id) if row.job_id else None,
        }
    return out


def _company_knowledge_context(organization_id: UUID, output_type: str) -> str:
    """Retrieve relevant company Knowledge Base chunks for grounding.

    Uses the org-scoped ``company_knowledge`` RAG collection. Legal/compliance
    files are excluded (read-only reference, not for question generation).
    Returns "" silently if the KB is empty or the vector store is unavailable.
    """
    try:
        from app.services.company_knowledge import search_company_knowledge

        query = (
            "company culture, values, work environment, team norms, "
            "ways of working, expectations, behaviours we value"
            if output_type == "hr_questions"
            else "company overview, culture, role expectations, what success looks like"
        )
        hits = search_company_knowledge(
            organization_id, query, limit=6, include_legal=False,
        )
        texts: list[str] = []
        for h in hits:
            payload = h.get("payload") or {}
            text = payload.get("text")
            if text:
                fname = payload.get("file_name") or "company file"
                texts.append(f"[{fname}] {text}")
        joined = "\n".join(texts).strip()
        return joined[:4000]
    except Exception:  # noqa: BLE001
        logger.warning(
            "[PreparationAgent] company knowledge lookup skipped (org=%s)",
            organization_id, exc_info=True,
        )
        return ""


def _deterministic_fallback(
    output_type: PreparationOutputType,
    ctx: dict[str, Any],
    *,
    error: str,
) -> dict[str, Any]:
    """Last-ditch payload so the UI always has something useful to render."""
    job_title = (ctx.get("job") or {}).get("title") or "the role"
    if output_type == "pre_analysis":
        return {
            "summary": (
                f"Preparation agent unavailable ({error[:80]}). The candidate "
                f"is being evaluated for {job_title}; review skills + evidence "
                "directly on the profile."
            ),
            "strengths": [],
            "possible_gaps": [],
            "risk_flags": [],
            "recommended_focus_areas": [],
            "interview_strategy": [],
            "agent_error": error[:300],
        }
    if output_type in ("technical_questions", "hr_questions"):
        return {"questions": [], "agent_error": error[:300]}
    return {  # assessment
        "title": "",
        "objective": "",
        "instructions": [],
        "expected_deliverables": [],
        "time_estimate": "",
        "evaluation_rubric": [],
        "agent_error": error[:300],
    }
