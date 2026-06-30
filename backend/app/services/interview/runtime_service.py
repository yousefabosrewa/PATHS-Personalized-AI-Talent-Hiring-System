"""
PATHS Backend — Interview Intelligence runtime service.

Records turn-by-turn Q&A into the existing ``interview_transcripts`` table
(stored as JSON inside ``transcript_text``), generates adaptive follow-up
questions, and finalises a session.

No new tables — every existing model is reused. The transcript is stored
as a JSON document with shape::

    {
      "kind": "live_ai_interview",
      "turns": [
        {"index": 1, "question": "...", "answer": "...", "asked_at": "ISO", "answered_at": "ISO", "is_followup": false, "parent_index": null},
        ...
      ],
      "completed": false
    }

A row in ``interview_transcripts`` with ``transcript_source='live_ai_interview'``
holds the live state. Calling ``finalize_session`` flips ``completed=true``
and sets the parent ``Interview.status`` to ``completed``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.candidate import Candidate
from app.db.models.interview import (
    Interview,
    InterviewQuestionPack,
    InterviewTranscript,
)
from app.db.models.job import Job
from app.services.interview.interview_audit import log_interview_action
from app.services.llm_provider import LLMProviderError, generate_json

logger = logging.getLogger(__name__)
settings = get_settings()


_LIVE_SOURCE = "live_ai_interview"


# ── DTOs ─────────────────────────────────────────────────────────────────


@dataclass
class TurnInput:
    question: str
    answer: str
    is_followup: bool = False
    parent_index: int | None = None


@dataclass
class TurnRecord:
    index: int
    question: str
    answer: str
    asked_at: str
    answered_at: str
    is_followup: bool = False
    parent_index: int | None = None


# ── Internal helpers ─────────────────────────────────────────────────────


def _get_or_create_live_transcript(
    db: Session, *, interview_id: UUID,
) -> InterviewTranscript:
    row = db.execute(
        select(InterviewTranscript)
        .where(
            InterviewTranscript.interview_id == interview_id,
            InterviewTranscript.transcript_source == _LIVE_SOURCE,
        )
        .order_by(InterviewTranscript.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = InterviewTranscript(
        interview_id=interview_id,
        transcript_source=_LIVE_SOURCE,
        transcript_text=json.dumps(
            {"kind": _LIVE_SOURCE, "turns": [], "completed": False}
        ),
    )
    db.add(row)
    db.flush()
    return row


def _load_doc(transcript: InterviewTranscript) -> dict[str, Any]:
    text = (transcript.transcript_text or "").strip()
    if not text:
        return {"kind": _LIVE_SOURCE, "turns": [], "completed": False}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Legacy free-text transcript — wrap it as a single turn.
        return {
            "kind": _LIVE_SOURCE,
            "turns": [
                {
                    "index": 1,
                    "question": "Imported transcript",
                    "answer": text,
                    "asked_at": None,
                    "answered_at": None,
                    "is_followup": False,
                    "parent_index": None,
                }
            ],
            "completed": False,
        }
    if not isinstance(data, dict):
        return {"kind": _LIVE_SOURCE, "turns": [], "completed": False}
    data.setdefault("kind", _LIVE_SOURCE)
    data.setdefault("turns", [])
    data.setdefault("completed", False)
    return data


def _save_doc(transcript: InterviewTranscript, doc: dict[str, Any]) -> None:
    transcript.transcript_text = json.dumps(doc, ensure_ascii=False)


def _flatten_turns(turns: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for t in turns or []:
        q = (t.get("question") or "").strip()
        a = (t.get("answer") or "").strip()
        if not q and not a:
            continue
        marker = " (follow-up)" if t.get("is_followup") else ""
        parts.append(f"Q{t.get('index') or ''}{marker}: {q}\nA: {a}".strip())
    return "\n\n".join(parts)


# ── Public operations ────────────────────────────────────────────────────


def record_answer(
    db: Session, *, interview_id: UUID, turn: TurnInput,
) -> TurnRecord:
    """Append one Q&A turn to the live transcript."""
    transcript = _get_or_create_live_transcript(db, interview_id=interview_id)
    doc = _load_doc(transcript)
    if doc.get("completed"):
        raise ValueError("interview_already_completed")
    turns: list[dict[str, Any]] = doc.get("turns") or []
    if len(turns) >= int(settings.interview_runtime_max_turns):
        raise ValueError("interview_max_turns_reached")
    now = datetime.now(timezone.utc).isoformat()
    rec: dict[str, Any] = {
        "index": len(turns) + 1,
        "question": (turn.question or "").strip()[:4000],
        "answer": (turn.answer or "").strip()[:8000],
        "asked_at": now,
        "answered_at": now,
        "is_followup": bool(turn.is_followup),
        "parent_index": (
            int(turn.parent_index) if turn.parent_index is not None else None
        ),
    }
    if not rec["question"] or not rec["answer"]:
        raise ValueError("question_and_answer_required")
    turns.append(rec)
    doc["turns"] = turns
    _save_doc(transcript, doc)
    db.commit()
    log_interview_action(
        db,
        actor_user_id=None,
        action="interview.answer_recorded",
        entity_id=interview_id,
        extra={
            "turn_index": rec["index"],
            "is_followup": rec["is_followup"],
        },
    )
    return TurnRecord(**rec)


def list_turns(
    db: Session, *, interview_id: UUID,
) -> tuple[list[TurnRecord], bool]:
    transcript = db.execute(
        select(InterviewTranscript)
        .where(
            InterviewTranscript.interview_id == interview_id,
            InterviewTranscript.transcript_source == _LIVE_SOURCE,
        )
        .order_by(InterviewTranscript.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if transcript is None:
        return [], False
    doc = _load_doc(transcript)
    return [TurnRecord(**t) for t in doc.get("turns") or []], bool(doc.get("completed"))


def generate_followup(
    db: Session,
    *,
    interview_id: UUID,
    parent_index: int,
) -> str:
    """Generate ONE follow-up question targeted at a specific previous turn."""
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise ValueError("interview_not_found")
    transcript = _get_or_create_live_transcript(db, interview_id=interview_id)
    doc = _load_doc(transcript)
    turns: list[dict[str, Any]] = doc.get("turns") or []
    parent = next(
        (t for t in turns if int(t.get("index", -1)) == int(parent_index)), None,
    )
    if parent is None:
        raise ValueError("parent_turn_not_found")

    job = db.get(Job, interview.job_id) if interview.job_id else None
    cand = (
        db.get(Candidate, interview.candidate_id) if interview.candidate_id else None
    )
    job_brief = (
        f"{job.title} (seniority {job.seniority_level or 'unspecified'}). "
        f"Responsibilities/summary: {(job.summary or job.description_text or '')[:600]}"
        if job is not None
        else "Open role"
    )
    cand_brief = (
        f"Candidate {cand.full_name} ({cand.current_title or '—'}, "
        f"{cand.years_experience or '—'} yrs). Skills: "
        f"{', '.join((cand.skills or [])[:8]) or '—'}"
        if cand is not None
        else "Candidate"
    )
    transcript_blob = _flatten_turns(turns)[:3500]
    prior_followups = [
        t for t in turns
        if t.get("is_followup")
        and int(t.get("parent_index", -1)) == int(parent_index)
    ]

    system = (
        "You are a senior recruiter conducting a structured interview. "
        "Ask ONE follow-up question that probes the candidate's previous answer. "
        "Do not ask anything about religion, politics, family status, health, "
        "disability, age, race, or gender. Stay strictly within the role "
        "context. Reply with ONLY a JSON object: {\"question\": \"<one short "
        "question>\"}"
    )
    user = (
        f"Job: {job_brief}\n\n"
        f"Candidate: {cand_brief}\n\n"
        f"Conversation so far:\n{transcript_blob}\n\n"
        f"Previous question (Q{parent.get('index')}): {parent.get('question')}\n"
        f"Candidate answer: {parent.get('answer')}\n\n"
        f"Number of follow-ups already asked for this question: {len(prior_followups)}\n\n"
        "Generate one focused follow-up that clarifies vagueness, requests an "
        "example, or probes depth on a relevant skill. Return JSON only."
    )

    try:
        data = generate_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=200,
        )
    except LLMProviderError as exc:
        logger.warning("[Interview][FollowUp] LLM failed: %s", exc)
        return _fallback_followup(parent)

    question = ""
    if isinstance(data, dict):
        question = str(data.get("question") or "").strip()
    if not question:
        return _fallback_followup(parent)
    return question[:600]


def _fallback_followup(parent: dict[str, Any]) -> str:
    return (
        "Could you walk me through a concrete example of how you handled that, "
        "including what was tricky and what the outcome was?"
    )


def finalize_session(
    db: Session, *, interview_id: UUID,
) -> dict[str, Any]:
    """Mark the live transcript completed and the Interview as completed."""
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise ValueError("interview_not_found")
    transcript = _get_or_create_live_transcript(db, interview_id=interview_id)
    doc = _load_doc(transcript)
    if doc.get("completed"):
        return {
            "ok": True,
            "already_completed": True,
            "turn_count": len(doc.get("turns") or []),
        }
    turns = doc.get("turns") or []
    if not turns:
        raise ValueError("no_turns_recorded")
    doc["completed"] = True
    doc["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_doc(transcript, doc)
    interview.status = "completed"
    db.commit()
    log_interview_action(
        db,
        actor_user_id=None,
        action="interview.session_completed",
        entity_id=interview_id,
        extra={"turn_count": len(turns)},
    )
    return {"ok": True, "turn_count": len(turns)}


def render_plain_transcript(db: Session, *, interview_id: UUID) -> str:
    """Return the live Q&A as a plain-text transcript (used by analyze)."""
    turns, _ = list_turns(db, interview_id=interview_id)
    return _flatten_turns([t.__dict__ for t in turns])


def get_questions_flat(
    db: Session, *, interview_id: UUID,
) -> list[dict[str, Any]]:
    """Flatten all approved/draft question packs into a single list."""
    packs = list(
        db.execute(
            select(InterviewQuestionPack).where(
                InterviewQuestionPack.interview_id == interview_id,
            )
        ).scalars().all()
    )
    out: list[dict[str, Any]] = []
    for p in packs:
        body = p.questions_json if isinstance(p.questions_json, dict) else {}
        questions = body.get("questions") if isinstance(body, dict) else None
        if not isinstance(questions, list):
            continue
        for i, q in enumerate(questions):
            if isinstance(q, str):
                out.append({"text": q, "category": p.question_pack_type, "pack_id": str(p.id), "order": i})
            elif isinstance(q, dict):
                out.append(
                    {
                        "text": str(q.get("text") or q.get("question") or ""),
                        "category": str(
                            q.get("category") or p.question_pack_type or "general",
                        ),
                        "skills": q.get("skills") or [],
                        "pack_id": str(p.id),
                        "order": i,
                    }
                )
    return out


__all__ = [
    "TurnInput",
    "TurnRecord",
    "finalize_session",
    "generate_followup",
    "get_questions_flat",
    "list_turns",
    "record_answer",
    "render_plain_transcript",
]
