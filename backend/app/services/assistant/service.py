"""
PATHS Backend — In-app context-aware assistant.

A floating support chatbot whose answers are grounded in the page the user is
currently on. The frontend sends a ``context_key`` (e.g. "dashboard", "jobs",
"candidate") and an optional ``entity_id`` (a job/candidate id); this service
builds a grounding block for that context (live DB data for a specific job or
candidate, a curated description for section pages), replays the recent
conversation for that exact context (hybrid memory: persistent rows +
short-term working window), and asks the LLM for a concise, page-specific
reply. Falls back to a deterministic guide when the LLM is unavailable.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import engine
from app.db.models.application import Application
from app.db.models.assistant import AssistantMessage
from app.db.models.candidate import Candidate
from app.db.models.hitl import HITLApproval
from app.db.models.interview import Interview
from app.db.models.job import Job
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_chat_response,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Replayed into the prompt as short-term working memory (turns, not rows).
_HISTORY_WINDOW = 16
_MAX_MESSAGE_CHARS = 4000

_table_ready = False


def ensure_table() -> None:
    """Create assistant_messages on first use (Alembic is bypassed here)."""
    global _table_ready
    if _table_ready:
        return
    AssistantMessage.__table__.create(bind=engine, checkfirst=True)
    _table_ready = True


# ── Section guides: accurate, app-specific descriptions for list/section pages.
# (label, what-the-page-is-for). Entity pages (job/candidate) add live data.
_SECTION_GUIDE: dict[str, tuple[str, str]] = {
    "dashboard": (
        "Dashboard",
        "The recruiter home overview: active jobs, candidates in the pipeline, "
        "pending approvals and recent AI agent activity. It's the starting point "
        "for navigating to jobs, candidates and the hiring workflow.",
    ),
    "jobs": (
        "Jobs",
        "The list of this organisation's job postings. From here you can create "
        "a job, edit it, archive or delete it (via the 3-dots menu), and open a "
        "job to its tabs: Overview, Screening, Candidates, Assessment, "
        "Interviews and Decision. Each job card shows a pipeline breakdown.",
    ),
    "candidates": (
        "Candidates pipeline",
        "Every candidate across all jobs with their pipeline stage, the job they "
        "applied to, and their match score. Recruiter names are anonymised until "
        "a de-anonymisation request is approved. Click a candidate to open their "
        "profile.",
    ),
    "approvals": (
        "Approvals",
        "Human-in-the-loop gates that the AI agents raise — for example outreach "
        "messages or hiring decisions that need a person to approve or reject "
        "before anything happens. Agents recommend; a human always decides.",
    ),
    "assessment": (
        "Assessment",
        "Online skills assessments for this job. Send a test to a candidate, then "
        "review their submission and graded score. The score feeds the decision "
        "rubric.",
    ),
    "interviews": (
        "Interviews",
        "Schedule HR, technical or mixed interviews, generate tailored question "
        "packs, run the interview analysis, and view per-type scores. If nobody "
        "joins a scheduled interview it auto-scores 0 unless rescheduled.",
    ),
    "decision": (
        "Decision Support (IDSS)",
        "The Intelligent Decision Support page: a stage-weighted rubric with the "
        "candidate's score, the AI recommendation, confidence, a per-stage "
        "breakdown, the HR manager's final decision, and a generated development "
        "plan. The human makes the final hire/reject call.",
    ),
    "screening": (
        "Screening",
        "Run screening to surface the top candidates from your source database "
        "scored against this job, then add the ones you want into the hiring "
        "process.",
    ),
    "source_candidate": (
        "Source Candidate",
        "Find candidates already in your database, with Explain (why they fit) "
        "and Shortlist per row. Use Find Talent to search and rank candidates "
        "against a job or a free-text brief.",
    ),
    "members": (
        "Team Members",
        "Invite recruiters, HR and hiring managers to your organisation, set "
        "their role, preview and approve the invitation email, and resend or "
        "remove members.",
    ),
    "general": (
        "PATHS",
        "PATHS is an evidence-driven, human-in-the-loop hiring platform powered "
        "by AI agents that source, screen, interview and support hiring "
        "decisions — while a human approves every important step.",
    ),
}


def _clip(text: str | None, n: int = 600) -> str:
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _job_grounding(db: Session, organization_id: uuid.UUID, entity_id: str) -> str:
    try:
        job = db.get(Job, uuid.UUID(entity_id))
    except (ValueError, TypeError):
        job = None
    if job is None or job.organization_id != organization_id:
        return "This job could not be loaded (it may not belong to your organisation)."
    n_apps = db.execute(
        select(Application.id).where(Application.job_id == job.id)
    ).scalars().all()
    lines = [
        f"Job title: {job.title}",
        f"Status: {getattr(job, 'status', '—')} | Seniority: {job.seniority_level or '—'}"
        f" | Location: {job.location_text or '—'} | Type: {job.employment_type or '—'}",
        f"Applicants in pipeline: {len(n_apps)}",
    ]
    if job.summary or job.description_text:
        lines.append(f"Summary: {_clip(job.summary or job.description_text, 700)}")
    if job.requirements:
        lines.append(f"Requirements: {_clip(job.requirements, 700)}")
    return "\n".join(lines)


def _candidate_grounding(
    db: Session, organization_id: uuid.UUID, entity_id: str,
) -> str:
    try:
        cand = db.get(Candidate, uuid.UUID(entity_id))
    except (ValueError, TypeError):
        cand = None
    if cand is None:
        return "This candidate could not be loaded."
    lines = [
        f"Candidate: {cand.full_name or 'Unknown'}",
        f"Current title: {cand.current_title or '—'} | Location: {cand.location_text or '—'}"
        f" | Experience: {cand.years_experience if cand.years_experience is not None else '—'} yrs",
    ]
    if cand.headline:
        lines.append(f"Headline: {_clip(cand.headline, 300)}")
    skills = list(cand.skills or [])
    lines.append(
        "Skills: " + (", ".join(skills[:25]) if skills else "none recorded yet")
    )
    if cand.summary:
        lines.append(f"Summary: {_clip(cand.summary, 700)}")
    # Their applications in this org (job title + stage), so the assistant can
    # talk about where this candidate is in the process.
    try:
        rows = db.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(
                Application.candidate_id == cand.id,
                Job.organization_id == organization_id,
            )
        ).all()
        if rows:
            apps = "; ".join(
                f"{job.title} (stage: {app.current_stage_code}, status: {app.overall_status})"
                for app, job in rows[:8]
            )
            lines.append(f"Applications: {apps}")
    except Exception:  # noqa: BLE001 — grounding must never break the chat
        logger.debug("candidate applications grounding failed", exc_info=True)
    lines.append(
        "On this profile you can run CV pre-analysis, generate technical or "
        "HR/behavioural interview questions, summarise the profile, and get a "
        "fit recommendation against a job."
    )
    return "\n".join(lines)


# ── Live page data: the REAL records currently on a list/section page, so
# PATHy can answer "who is on this page", "how many", "list them", etc.

def _dashboard_live(db: Session, org: uuid.UUID) -> str:
    jobs = db.execute(
        select(func.count()).select_from(Job).where(Job.organization_id == org)
    ).scalar() or 0
    active = db.execute(
        select(func.count()).select_from(Job).where(
            Job.organization_id == org, Job.is_active == True,  # noqa: E712
        )
    ).scalar() or 0
    apps = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == org)
    ).scalar() or 0
    pending = db.execute(
        select(func.count()).select_from(HITLApproval).where(
            HITLApproval.organization_id == org, HITLApproval.status == "pending",
        )
    ).scalar() or 0
    return (
        "LIVE DASHBOARD DATA:\n"
        f"- Jobs: {jobs} ({active} active)\n"
        f"- Candidates in the pipeline (applications): {apps}\n"
        f"- Pending approvals: {pending}"
    )


def _jobs_live(db: Session, org: uuid.UUID) -> str:
    rows = db.execute(
        select(Job).where(Job.organization_id == org)
        .order_by(Job.created_at.desc()).limit(25)
    ).scalars().all()
    if not rows:
        return "LIVE PAGE DATA: there are no jobs yet."
    lines = [f"- {j.title} (status: {getattr(j, 'status', '—')})" for j in rows]
    return f"LIVE PAGE DATA — {len(rows)} job(s) currently listed:\n" + "\n".join(lines)


def _candidates_live(db: Session, org: uuid.UUID) -> str:
    rows = db.execute(
        select(Application, Candidate, Job)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Job.organization_id == org)
        .order_by(Application.created_at.desc()).limit(25)
    ).all()
    if not rows:
        return "LIVE PAGE DATA: no candidates in the pipeline yet."
    lines = [
        f"- {c.full_name or 'Unknown'} — {j.title} "
        f"(stage: {a.current_stage_code}, status: {a.overall_status})"
        for a, c, j in rows
    ]
    return f"LIVE PAGE DATA — {len(rows)} candidate(s) in the pipeline:\n" + "\n".join(lines)


def _source_candidate_live(db: Session, org: uuid.UUID) -> str:
    from app.services.source_candidate.service import SourceCandidateService

    cands = SourceCandidateService().list_database_candidates(
        db, organization_id=org, limit=25,
    )
    if not cands:
        return "LIVE PAGE DATA: the candidate database is empty for this organisation."
    lines = []
    for c in cands:
        sk = ", ".join((c.skills or [])[:6]) or "no skills recorded"
        lines.append(f"- {c.full_name or 'Unknown'} — {c.current_title or '—'} | skills: {sk}")
    return (
        f"LIVE PAGE DATA — {len(cands)} candidate(s) in your database "
        f"(the list shown on this page):\n" + "\n".join(lines)
    )


def _approvals_live(db: Session, org: uuid.UUID) -> str:
    rows = db.execute(
        select(HITLApproval).where(
            HITLApproval.organization_id == org, HITLApproval.status == "pending",
        ).order_by(HITLApproval.requested_at.desc()).limit(25)
    ).scalars().all()
    if not rows:
        return "LIVE PAGE DATA: there are no pending approvals right now."
    lines = [
        f"- {r.action_type} · {r.entity_label or r.entity_type} "
        f"(priority: {r.priority}, requested by: {r.requested_by_name})"
        for r in rows
    ]
    return f"LIVE PAGE DATA — {len(rows)} pending approval(s):\n" + "\n".join(lines)


def _interviews_live(db: Session, org: uuid.UUID) -> str:
    rows = db.execute(
        select(Interview, Candidate, Job)
        .join(Candidate, Candidate.id == Interview.candidate_id, isouter=True)
        .join(Job, Job.id == Interview.job_id, isouter=True)
        .where(Interview.organization_id == org)
        .order_by(Interview.updated_at.desc()).limit(25)
    ).all()
    if not rows:
        return "LIVE PAGE DATA: no interviews have been scheduled yet."
    lines = [
        f"- {(c.full_name if c else 'Unknown')} — {(j.title if j else '—')} "
        f"({iv.interview_type}, status: {iv.status})"
        for iv, c, j in rows
    ]
    return f"LIVE PAGE DATA — {len(rows)} interview(s):\n" + "\n".join(lines)


_LIVE_BUILDERS = {
    "dashboard": _dashboard_live,
    "jobs": _jobs_live,
    "candidates": _candidates_live,
    "source_candidate": _source_candidate_live,
    "approvals": _approvals_live,
    "interviews": _interviews_live,
}


def _live_block(db: Session, org: uuid.UUID, key: str) -> str:
    builder = _LIVE_BUILDERS.get(key)
    if builder is None:
        return ""
    try:
        return builder(db, org)
    except Exception:  # noqa: BLE001 — live data is best-effort, never fatal
        logger.debug("live grounding failed for %s", key, exc_info=True)
        return ""


def build_context(
    db: Session,
    *,
    organization_id: uuid.UUID,
    context_key: str,
    entity_id: str,
) -> tuple[str, str]:
    """Return (human label, grounding text) for the given page context.

    Section/list pages get the page description PLUS the live records currently
    on that page, so PATHy can answer questions about what's actually there.
    """
    key = (context_key or "general").strip().lower()
    if key in ("candidate", "candidate_profile") and entity_id:
        return "Candidate profile", _candidate_grounding(db, organization_id, entity_id)
    if key in ("job", "job_overview") and entity_id:
        return "Job", _job_grounding(db, organization_id, entity_id)
    # job sub-tabs that carry a job entity: blend section guide + live job data.
    if entity_id and key in {"screening", "assessment", "interviews", "decision"}:
        label, desc = _SECTION_GUIDE.get(key, _SECTION_GUIDE["general"])
        return label, desc + "\n\nThis job:\n" + _job_grounding(db, organization_id, entity_id)
    label, desc = _SECTION_GUIDE.get(key, _SECTION_GUIDE["general"])
    live = _live_block(db, organization_id, key)
    return label, (desc + "\n\n" + live) if live else desc


def _system_prompt(label: str, grounding: str) -> str:
    return (
        "You are PATHy, the built-in AI assistant inside the PATHS hiring "
        "platform, helping a recruiter / HR user on the page they are viewing. "
        "Introduce yourself as PATHy when asked who you are.\n\n"
        "How to answer:\n"
        "- The CONTEXT below has a description of the page AND, when available, a "
        "'LIVE PAGE DATA' / 'LIVE DASHBOARD DATA' block listing the REAL records "
        "currently on the page. USE that live data to directly answer questions "
        "like 'who is on this page', 'how many', 'list them', 'which candidate "
        "has X', 'tell me about <name>'. Answer with the actual names/values — do "
        "NOT give a generic description when the data is right there.\n"
        "- When the user asks how to do something (e.g. 'how do I add a "
        "candidate', 'what are the steps'), give clear NUMBERED step-by-step "
        "instructions for doing it in PATHS.\n"
        "- Be direct, specific and genuinely helpful. Prefer concrete answers and "
        "bullet/numbered lists over vague descriptions.\n"
        "- Only use facts from the CONTEXT. If the exact data isn't there, say "
        "what you can see and where to find the rest. Never invent candidate or "
        "job data.\n"
        "- You assist and explain; you never take actions or make hiring "
        "decisions yourself.\n\n"
        f"CURRENT PAGE: {label}\n"
        f"CONTEXT:\n{grounding}"
    )


def _offline_reply(label: str, grounding: str, message: str) -> str:
    """Deterministic fallback when the LLM is unavailable, so the widget still
    answers with accurate page guidance."""
    return (
        f"I'm PATHy, your assistant for the **{label}** page. "
        "(The AI model is unavailable right now, so here's the page context.)\n\n"
        f"{grounding}\n\n"
        "Ask me again in a moment for a tailored answer."
    )


def load_history(
    db: Session,
    *,
    user_id: uuid.UUID,
    context_key: str,
    entity_id: str,
    limit: int = _HISTORY_WINDOW,
) -> list[AssistantMessage]:
    ensure_table()
    rows = db.execute(
        select(AssistantMessage)
        .where(
            AssistantMessage.user_id == user_id,
            AssistantMessage.context_key == context_key,
            AssistantMessage.entity_id == (entity_id or ""),
        )
        .order_by(AssistantMessage.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(rows))  # chronological


def chat(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    context_key: str,
    entity_id: str,
    message: str,
) -> str:
    """Persist the user turn, generate a grounded reply, persist + return it."""
    ensure_table()
    context_key = (context_key or "general").strip().lower()[:64]
    entity_id = (entity_id or "")[:64]
    message = (message or "").strip()[:_MAX_MESSAGE_CHARS]
    if not message:
        return "Ask me anything about this page and I'll help."

    label, grounding = build_context(
        db, organization_id=organization_id, context_key=context_key, entity_id=entity_id,
    )

    prior = load_history(
        db, user_id=user_id, context_key=context_key, entity_id=entity_id,
    )
    history = [{"role": m.role, "content": m.content} for m in prior]
    history.append({"role": "user", "content": message})

    try:
        reply = generate_chat_response(
            _system_prompt(label, grounding),
            history,
            model=settings.assistant_model,
            temperature=0.3,
            max_tokens=700,
        ).strip()
        if not reply:
            reply = _offline_reply(label, grounding, message)
    except OpenRouterClientError as exc:
        logger.warning("[assistant] LLM unavailable: %s", exc)
        reply = _offline_reply(label, grounding, message)
    except Exception:  # noqa: BLE001
        logger.exception("[assistant] unexpected chat error")
        reply = _offline_reply(label, grounding, message)

    db.add_all([
        AssistantMessage(
            organization_id=organization_id, user_id=user_id,
            context_key=context_key, entity_id=entity_id, role="user", content=message,
        ),
        AssistantMessage(
            organization_id=organization_id, user_id=user_id,
            context_key=context_key, entity_id=entity_id, role="assistant", content=reply,
        ),
    ])
    db.commit()
    return reply


def clear_history(
    db: Session,
    *,
    user_id: uuid.UUID,
    context_key: str,
    entity_id: str,
) -> int:
    ensure_table()
    result = db.execute(
        delete(AssistantMessage).where(
            AssistantMessage.user_id == user_id,
            AssistantMessage.context_key == (context_key or "general").strip().lower(),
            AssistantMessage.entity_id == (entity_id or ""),
        ),
        execution_options={"synchronize_session": False},
    )
    db.commit()
    return int(result.rowcount or 0)
