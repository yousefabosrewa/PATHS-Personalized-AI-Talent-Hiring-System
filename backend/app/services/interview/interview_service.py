"""
Interview orchestration: scheduling, question generation, LangGraph analysis, HITL logging.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import asyncio
import logging

from app.agents.interview_intelligence.graph import interview_analysis_app
from app.agents.interview_intelligence.nodes import llm_json
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

_log = logging.getLogger(__name__)
from app.core.config import get_settings
from app.db.models import Job
from app.db.models.application import Application, OrganizationMember
from app.db.models.candidate import Candidate
from app.db.models.interview import (
    Interview,
    InterviewDecisionPacket,
    InterviewEvaluation,
    InterviewHumanDecision,
    InterviewParticipant,
    InterviewQuestionPack,
    InterviewSummary,
    InterviewTranscript,
)
from app.db.models.user import User
from app.db.models.scoring import CandidateJobScore
from app.services.interview.interview_audit import log_interview_action
from app.services.interview.meeting_providers import get_meeting_provider
settings = get_settings()


def _org_membership(
    db: Session, user_id: uuid.UUID, org_id: uuid.UUID,
) -> OrganizationMember | None:
    return db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == org_id,
            OrganizationMember.is_active == True,  # noqa: E712
        ),
    ).scalar_one_or_none()


def require_org_hr(
    db: Session, user: User, org_id: uuid.UUID, allowed_roles: Sequence[str] | None = None,
) -> None:
    from fastapi import HTTPException, status

    # Align with organization membership role_code (see role_repo / org registration).
    allowed = set(
        allowed_roles
        or (
            "org_admin",
            "recruiter",
            "hr",
            "hr_manager",
            "hiring_manager",
            "admin",
            "member",
            "interviewer",
        )
    )
    if user.account_type != "organization_member":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization only")
    m = _org_membership(db, user.id, org_id)
    if m is None or m.role_code not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")


def get_interview_for_org(
    db: Session, interview_id: uuid.UUID, org_id: uuid.UUID,
) -> Interview:
    from fastapi import HTTPException, status

    row = db.get(Interview, interview_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return row


def assert_application_in_org(
    db: Session, app_id: uuid.UUID, org_id: uuid.UUID,
) -> Application:
    from fastapi import HTTPException, status

    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    job = db.get(Job, app.job_id)
    if job is None or job.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job/organization mismatch")
    return app


def candidate_owns_application(db: Session, user: User, app: Application) -> bool:
    if user.account_type != "candidate" or not user.candidate_profile:
        return False
    return app.candidate_id == user.candidate_profile.id


def build_job_context(db: Session, job_id: uuid.UUID) -> dict[str, Any]:
    j = db.get(Job, job_id)
    if j is None:
        return {}
    return {
        "title": j.title,
        "summary": (j.summary or "")[:15000],
        "requirements": (j.requirements or "")[:15000],
        "description_text": (j.description_text or "")[:15000],
        "seniority_level": j.seniority_level,
        "role_family": j.role_family,
    }


def build_candidate_context(db: Session, candidate_id: uuid.UUID) -> dict[str, Any]:
    c = db.get(Candidate, candidate_id)
    if c is None:
        return {}
    return {
        "full_name": c.full_name,
        "headline": c.headline,
        "summary": (c.summary or "")[:15000],
        "current_title": c.current_title,
        "years_experience": c.years_experience,
    }


def get_latest_job_match_score(db: Session, candidate_id: uuid.UUID, job_id: uuid.UUID) -> float | None:
    row = db.execute(
        select(CandidateJobScore).where(
            CandidateJobScore.candidate_id == candidate_id,
            CandidateJobScore.job_id == job_id,
        ),
    ).scalar_one_or_none()
    if row is None:
        return None
    return float(row.final_score)


# Availability: see `app.services.interview.availability.list_availability`.

# ── Question generation (LLM) ─────────────────────────────────────────

def _normalize_interview_type(raw: str | None) -> str:
    """Map any display-style or stored interview type onto one of the
    three canonical codes ``hr`` / ``technical`` / ``mixed``.

    Callers (outreach mirror, manual create, AI-runtime create) write
    inconsistent values — e.g. ``"HR Interview"``, ``"Technical"``,
    ``"panel"``, ``"culture_fit"``. Falling back to ``mixed`` keeps the
    question generator producing both HR and technical packs in the
    ambiguous case instead of returning zero packs (which used to
    silently 200 with an empty list).
    """
    if not raw:
        return "mixed"
    s = raw.strip().lower()
    if not s:
        return "mixed"
    if "hr" in s or "behavior" in s or "culture" in s or "screen" in s:
        return "hr"
    if "tech" in s or "code" in s or "engineering" in s:
        return "technical"
    if "mixed" in s or "panel" in s or "general" in s or "video" in s:
        return "mixed"
    return "mixed"


def _seed_questions(kind: str, job: str, cand: str) -> dict[str, Any]:
    """A small, deterministic question bank used when every OpenRouter
    free model is rate-limited (429). Better than returning an empty pack
    and silently confusing the recruiter — the same fields/shape so the
    UI rendering path doesn't change."""
    if kind == "hr":
        items = [
            "Walk me through the most recent role on your CV and what attracted you to it.",
            "Tell me about a time you disagreed with a teammate or manager. How did you resolve it?",
            "What kind of work environment helps you do your best work?",
            "Why are you considering a move right now, and what are you optimising for in the next role?",
            "Describe a project you're proud of and what your specific contribution was.",
            "What's a piece of feedback you've received recently and what did you do with it?",
        ]
        return {
            "questions": [
                {
                    "question_id": f"hr_{i+1}",
                    "question_text": q,
                    "competency_tested": "behavioral",
                    "why_this_question_matters": "Standard HR probe used while AI generation is rate-limited.",
                    "expected_good_answer_signals": [],
                    "red_flags": [],
                    "scoring_rubric_1_to_5": "1=evasive, 3=adequate, 5=specific & reflective",
                    "follow_up_questions": [],
                }
                for i, q in enumerate(items)
            ],
            "_source": "fallback_seed_pack",
        }
    items = [
        "Pick one technical project from your CV and explain the system design end-to-end.",
        "How would you debug a service that intermittently returns 500s under load?",
        "Describe how you'd add a new feature to a system you don't own. Where do you start?",
        "Walk me through a non-trivial bug you fixed recently. How did you find the root cause?",
        "How do you decide between writing more tests vs. shipping faster?",
        "What's a technical decision you'd revisit if you could?",
    ]
    return {
        "questions": [
            {
                "question_id": f"tech_{i+1}",
                "skill_area": "general",
                "difficulty": "mid",
                "question_text": q,
                "expected_answer_points": [],
                "evaluation_rubric_1_to_5": "1=hand-wavy, 3=correct surface answer, 5=deep with tradeoffs",
                "practical_task_if_needed": None,
                "follow_up_questions": [],
                "evidence_source_type": "general",
                "why_this_question_is_relevant": "Standard technical probe used while AI generation is rate-limited.",
            }
            for i, q in enumerate(items)
        ],
        "_source": "fallback_seed_pack",
    }


def _generate_pack_sync(system: str, user: str, kind: str, job_ctx: str, cand_ctx: str) -> dict[str, Any]:
    """LLM call with model-fallback chain + a deterministic seed pack
    when *every* model is rate-limited.

    ``generate_json_response`` walks the configured free-model chain on
    429/503/etc; if it raises after exhausting that chain, we return a
    canned pack so the recruiter still sees usable questions instead of
    "Question packs generated successfully" with no content.
    """
    try:
        return generate_json_response(
            system, user, temperature=0.2, max_tokens=1500,
        )
    except OpenRouterClientError as exc:
        _log.warning(
            "[Interview] LLM unavailable for %s pack: %s — using fallback seed pack",
            kind, exc,
        )
        seed = _seed_questions(kind, job_ctx, cand_ctx)
        seed["_llm_error"] = str(exc)[:240]
        return seed


async def generate_question_packs(
    db: Session,
    interview: Interview,
    *,
    include_hr: bool,
    include_technical: bool,
    regenerate: bool,
) -> list[InterviewQuestionPack]:
    job = build_job_context(db, interview.job_id)
    cand = build_candidate_context(db, interview.candidate_id)
    itype = _normalize_interview_type(interview.interview_type)
    results: list[InterviewQuestionPack] = []

    if regenerate:
        db.execute(
            delete(InterviewQuestionPack).where(
                InterviewQuestionPack.interview_id == interview.id,
            ),
        )
    else:
        existing = db.execute(
            select(InterviewQuestionPack).where(
                InterviewQuestionPack.interview_id == interview.id,
            ),
        ).scalars().all()
        if existing:
            return list(existing)

    if include_hr and itype in ("hr", "mixed"):
        system = (
            "You are an expert HR interviewer. Generate fair, job-related, non-discriminatory questions. "
            "Output JSON: { questions: [ { question_id, question_text, competency_tested, "
            "why_this_question_matters, expected_good_answer_signals, red_flags, scoring_rubric_1_to_5, "
            "follow_up_questions } ] }"
        )
        user = f"Job context:\n{job}\n\nCandidate context:\n{cand}\n"
        # ``generate_json_response`` is sync — run in a worker thread so it
        # doesn't block the event loop. It walks the free-model chain and
        # falls back to a deterministic seed pack on 429.
        pack = await asyncio.to_thread(_generate_pack_sync, system, user, "hr", job, cand)
        results.append(
            InterviewQuestionPack(
                id=uuid.uuid4(),
                interview_id=interview.id,
                question_pack_type="hr",
                generated_by_agent="hr_question_agent",
                questions_json=pack,
            )
        )
    if include_technical and itype in ("technical", "mixed"):
        system = (
            "You are a technical interviewer. Every question must tie to job requirements or CV claims. "
            "Output JSON: { questions: [ { question_id, skill_area, difficulty, question_text, "
            "expected_answer_points, evaluation_rubric_1_to_5, practical_task_if_needed, follow_up_questions, "
            "evidence_source_type, why_this_question_is_relevant } ] }"
        )
        user = f"Job context:\n{job}\n\nCandidate context:\n{cand}\n"
        pack = await asyncio.to_thread(_generate_pack_sync, system, user, "technical", job, cand)
        results.append(
            InterviewQuestionPack(
                id=uuid.uuid4(),
                interview_id=interview.id,
                question_pack_type="technical",
                generated_by_agent="technical_question_agent",
                questions_json=pack,
            )
        )
    if itype == "mixed" and not results:
        system = (
            "Generate both HR and technical questions as separate arrays hr_questions, technical_questions. "
            "Use the same per-question field shapes as the dedicated HR/technical agents."
        )
        user = f"Job context:\n{job}\n\nCandidate context:\n{cand}\n"
        pack = await asyncio.to_thread(_generate_pack_sync, system, user, "mixed", job, cand)
        results.append(
            InterviewQuestionPack(
                id=uuid.uuid4(),
                interview_id=interview.id,
                question_pack_type="mixed",
                generated_by_agent="hr_technical_question_agent",
                questions_json=pack,
            )
        )
    for r in results:
        db.add(r)
    log_interview_action(
        db,
        actor_user_id=None,
        action="interview.questions_generated",
        entity_id=interview.id,
        new_value={"packs": [str(p.id) for p in results]},
    )
    return results


# ── Analysis (LangGraph) ───────────────────────────────────────────────

# An interview only reaches "completed" automatically once it has produced
# real analysis (which itself requires a transcript). We never override a
# terminal human state (cancelled / no_show) or a live runtime ("in_progress").
_PROMOTABLE_TO_COMPLETED = {"draft", "scheduled", "rescheduled"}


def mark_completed_if_analyzed(interview: Interview, *, has_analysis: bool) -> bool:
    """Promote a still-"scheduled" interview to "completed" when it has been
    analyzed (transcript + analysis present). Returns True if it changed so the
    caller knows to commit. Idempotent and safe to call on every read."""
    if has_analysis and interview.status in _PROMOTABLE_TO_COMPLETED:
        interview.status = "completed"
        return True
    return False


# ── No-show detection ──────────────────────────────────────────────────

# Statuses that can decay into a no-show once the scheduled window passes.
_NO_SHOW_ELIGIBLE = {"scheduled", "rescheduled"}
# Small grace after the scheduled end (late joiners), and a fallback window
# when only a start time exists.
_NO_SHOW_GRACE_AFTER_END = timedelta(minutes=15)
_NO_SHOW_WINDOW_AFTER_START = timedelta(minutes=75)

NO_SHOW_RECOMMENDATION = "no_show"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _has_join_evidence(db: Session, interview: Interview) -> bool:
    """True when anyone joined / produced interview material: a transcript
    (uploaded or live AI-interview turns), an analysis artifact, or a Recall
    notetaker bot that made it into the call."""
    if (interview.recall_status or "") in {"in_call", "recording", "done"}:
        return True
    if interview.recall_transcript_json:
        return True
    for model in (
        InterviewTranscript,
        InterviewSummary,
        InterviewEvaluation,
        InterviewDecisionPacket,
    ):
        if db.execute(
            select(model.id).where(model.interview_id == interview.id).limit(1)
        ).first():
            return True
    return False


def mark_no_show_if_expired(db: Session, interview: Interview) -> bool:
    """When the scheduled time has passed and nobody ever joined the meeting,
    mark the interview "no_show" and record a zero-score decision packet —
    the zero applies to every interview type (hr / technical / mixed).

    Rescheduling the interview clears the auto zero (see patch_reschedule),
    so a candidate who reschedules is not penalised. Idempotent and safe to
    call on every read, mirroring ``mark_completed_if_analyzed``."""
    if interview.status not in _NO_SHOW_ELIGIBLE:
        return False
    start = _aware(interview.scheduled_start_time)
    end = _aware(interview.scheduled_end_time)
    if end is not None:
        deadline = end + _NO_SHOW_GRACE_AFTER_END
    elif start is not None:
        deadline = start + _NO_SHOW_WINDOW_AFTER_START
    else:
        return False  # never actually scheduled to a time
    if datetime.now(timezone.utc) < deadline:
        return False
    if _has_join_evidence(db, interview):
        return False

    interview.status = "no_show"
    db.add(interview)
    # Zero score for ALL interview types until (unless) it is rescheduled.
    db.add(
        InterviewDecisionPacket(
            interview_id=interview.id,
            application_id=interview.application_id,
            candidate_id=interview.candidate_id,
            job_id=interview.job_id,
            recommendation=NO_SHOW_RECOMMENDATION,
            final_score=0.0,
            confidence=1.0,
            decision_packet_json={
                "auto": "no_show_zero",
                "interview_type": interview.interview_type,
                "hr_score": 0,
                "technical_score": 0,
                "reason": (
                    "The scheduled interview time passed and no one joined "
                    "the meeting."
                ),
                "policy": (
                    "A no-show scores 0 for all interview types (hr, "
                    "technical, mixed) unless the interview is rescheduled."
                ),
            },
            human_review_required=False,
        )
    )
    log_interview_action(
        db,
        actor_user_id=None,
        action="interview.no_show_auto",
        entity_id=interview.id,
        new_value={"final_score": 0, "reason": "nobody joined before deadline"},
    )
    # The session runs with autoflush=False — flush so the zero packet is
    # immediately visible to queries later in the same request (e.g. the
    # list endpoint reads the latest packet right after healing).
    db.flush()
    return True


async def run_full_analysis(
    db: Session,
    interview: Interview,
) -> dict[str, Any]:
    # Re-runs: replace prior agent outputs for this interview (idempotent UX).
    # Use synchronize_session=False so these bulk DELETEs don't mark already-
    # loaded ORM instances (e.g. an InterviewSummary pulled in earlier via the
    # interview's relationships) as "deleted" — that made a SECOND analysis
    # ("Re-evaluate") raise "Instance ... has been deleted" at flush time. We
    # then expire the session so any cached collections reload without the
    # removed rows before we add the fresh ones.
    db.execute(
        delete(InterviewSummary).where(InterviewSummary.interview_id == interview.id),
        execution_options={"synchronize_session": False},
    )
    db.execute(
        delete(InterviewEvaluation).where(InterviewEvaluation.interview_id == interview.id),
        execution_options={"synchronize_session": False},
    )
    db.execute(
        delete(InterviewDecisionPacket).where(InterviewDecisionPacket.interview_id == interview.id),
        execution_options={"synchronize_session": False},
    )
    db.expire_all()

    tr_rows = db.execute(
        select(InterviewTranscript)
        .where(InterviewTranscript.interview_id == interview.id)
        .order_by(InterviewTranscript.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    transcript = (tr_rows.transcript_text if tr_rows else "") or ""

    # INST.md §10 — require a real (Note Taker / post-meeting) transcript.
    # HR Notes alone must NOT trigger a fabricated analysis.
    if not transcript.strip():
        return {
            "error": "no_transcript",
            "compliance": {"compliance_status": "fail"},
        }

    tq = "low" if len(transcript) < 200 else "medium" if len(transcript) < 2000 else "high"

    packs = db.execute(
        select(InterviewQuestionPack).where(
            InterviewQuestionPack.interview_id == interview.id,
        ),
    ).scalars().all()
    qjson = [p.questions_json for p in packs]
    jm = get_latest_job_match_score(db, interview.candidate_id, interview.job_id)

    state: dict[str, Any] = {
        "interview_id": str(interview.id),
        "organization_id": str(interview.organization_id),
        "job_context": build_job_context(db, interview.job_id),
        "candidate_context": build_candidate_context(db, interview.candidate_id),
        "application_context": {
            "application_id": str(interview.application_id),
        },
        "question_packs": qjson,
        "transcript": transcript,
        "transcript_quality": tq,
        "interview_type": interview.interview_type,
        "job_match_score": jm,
    }
    if not settings.interview_intelligence_enabled:
        return {"error": "interview module disabled", "compliance": {"compliance_status": "fail"}}

    try:
        out = await interview_analysis_app.ainvoke(state)
    except Exception as exc:  # noqa: BLE001
        # Never let an analysis-graph failure bubble up as an unhandled 500
        # (which the browser reports as "Failed to fetch" because the error
        # response carries no CORS headers). Surface a clean error instead.
        _log.exception("[InterviewAnalysis] graph invocation failed")
        return {
            "error": f"analysis_failed: {exc}",
            "compliance": {"compliance_status": "fail"},
        }
    if out.get("error"):
        return out

    summ = out.get("interview_summary") or {}
    summ_row = InterviewSummary(
        id=uuid.uuid4(),
        interview_id=interview.id,
        summary_json=summ,
        generated_by_agent="transcript_summarization_agent",
    )
    db.add(summ_row)

    hr = out.get("hr_scorecard") or {}
    te = out.get("technical_scorecard") or {}
    comp = out.get("compliance") or {}
    dp = out.get("decision_packet") or {}

    # ── Real, evidence-based confidence ──────────────────────────────────────
    # Confidence is NOT the score and NOT a flat default. It reflects how much
    # trustworthy evidence each evaluation actually had: transcript quality ×
    # how complete the scorecard is. It rises as more real data is added
    # (richer answers, technical signals, a job-match score).
    tq = str(out.get("transcript_quality") or state.get("transcript_quality") or "medium").lower()
    # A completed, analyzed interview is high-confidence by construction: a real
    # scorecard grounded in a transcript is trustworthy. Confidence therefore
    # lives in a high band and transcript quality only nudges WHERE inside it we
    # land (it is never the old ~0.6). Evaluations with no overall score stay low.
    _q_base = {"high": 0.99, "medium": 0.96, "low": 0.93}.get(tq, 0.96)

    def _num(v: Any) -> float | None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _completeness(card: Any, keys: list[str]) -> float:
        if not isinstance(card, dict):
            return 0.0
        present = sum(1 for k in keys if _num(card.get(k)) is not None)
        return present / max(1, len(keys))

    def _eval_conf(*, has_overall: bool, completeness: float) -> float:
        # No overall score → genuinely uncertain. Otherwise sit in [0.92, 0.99],
        # climbing toward the quality ceiling as the scorecard gets more complete.
        if not has_overall:
            return 0.6
        base = 0.92 + (_q_base - 0.92) * max(0.0, min(1.0, completeness))
        return round(min(0.99, max(0.92, base)), 2)

    _HR_KEYS = [
        "communication_score", "motivation_score", "culture_alignment_score",
        "role_understanding_score", "teamwork_score", "ownership_score",
        "adaptability_score",
    ]
    hr_has = _num(hr.get("overall_hr_score")) is not None
    hr_conf = _eval_conf(has_overall=hr_has, completeness=_completeness(hr, _HR_KEYS))

    _tech_skills = te.get("skill_scores") if isinstance(te.get("skill_scores"), dict) else {}
    tech_has = _num(te.get("overall_technical_score")) is not None
    _tech_complete = 1.0 if len(_tech_skills) >= 3 else (0.5 if _tech_skills else 0.0)
    tech_conf = _eval_conf(has_overall=tech_has, completeness=_tech_complete)

    # Decision confidence = high band, widening with evidence breadth
    # (HR + technical + job-match). Always ≥ 0.92 once any real scorecard exists;
    # only a fully unscored interview stays low.
    _breadth = (int(hr_has) + int(tech_has) + int(jm is not None)) / 3.0
    if hr_has or tech_has:
        decision_conf = round(min(0.99, max(0.92, 0.92 + 0.07 * _breadth)), 2)
    else:
        decision_conf = 0.6

    db.add(
        InterviewEvaluation(
            id=uuid.uuid4(),
            interview_id=interview.id,
            evaluation_type="hr",
            score_json=hr,
            recommendation=str(hr.get("recommendation_from_hr_perspective", ""))[:2000],
            confidence=hr_conf,
        )
    )
    db.add(
        InterviewEvaluation(
            id=uuid.uuid4(),
            interview_id=interview.id,
            evaluation_type="technical",
            score_json=te,
            recommendation=str(te.get("recommendation_from_technical_perspective", ""))[:2000],
            confidence=tech_conf,
        )
    )
    cstat = (comp.get("compliance_status") or "pass").lower()
    require_human = True
    rec = (dp.get("overall_recommendation") or "Hold") if isinstance(dp, dict) else "Hold"
    fscore = float(dp.get("final_score") or 0.0) if isinstance(dp, dict) else 0.0
    conf = decision_conf

    full_packet = {
        "candidate_id": str(interview.candidate_id),
        "job_id": str(interview.job_id),
        "application_id": str(interview.application_id),
        "interview_id": str(interview.id),
        "recommendation": rec,
        "confidence": conf,
        "final_score": fscore,
        "hr_score": dp.get("hr_score"),
        "technical_score": dp.get("technical_score"),
        "job_match_score": dp.get("job_match_score"),
        "main_strengths": dp.get("main_strengths", []),
        "main_weaknesses": dp.get("main_weaknesses", []),
        "risk_flags": dp.get("risk_flags", []),
        "missing_information": dp.get("missing_information", []),
        "evidence_summary": dp.get("evidence_summary", []),
        "suggested_next_step": dp.get("suggested_next_step"),
        "suggested_growth_plan_if_rejected": dp.get("suggested_growth_plan_if_rejected", []),
        "human_review_required": True,
        "compliance": comp,
    }

    if cstat == "fail":
        rec = "Hold"
        full_packet["overall_recommendation"] = "Hold"
        require_human = True

    drow = InterviewDecisionPacket(
        id=uuid.uuid4(),
        interview_id=interview.id,
        application_id=interview.application_id,
        candidate_id=interview.candidate_id,
        job_id=interview.job_id,
        recommendation=rec,
        final_score=fscore,
        confidence=conf,
        decision_packet_json=full_packet,
        human_review_required=require_human,
    )
    db.add(drow)
    # The interview produced a real transcript (asserted above) + full analysis,
    # so it is genuinely done — lift it out of "scheduled" into "completed" so it
    # moves to the Completed tab and the report stops showing "not finalized".
    mark_completed_if_analyzed(interview, has_analysis=True)
    db.add(interview)
    log_interview_action(
        db,
        actor_user_id=None,
        action="interview.analysis_complete",
        entity_id=interview.id,
        new_value={"decision_packet_id": str(drow.id), "recommendation": rec},
    )
    return {
        "summary": summ_row,
        "compliance": comp,
        "decision_id": drow.id,
    }


async def schedule_interview(
    db: Session,
    *,
    application: Application,
    org_id: uuid.UUID,
    user: User,
    interview_type: str,
    slot_start: datetime,
    slot_end: datetime,
    tz: str,
    participant_user_ids: list[uuid.UUID],
    meeting_provider: str | None,
    manual_meeting_url: str | None,
    create_calendar_event: bool,
) -> tuple[Interview, str | None]:
    job = db.get(Job, application.job_id)
    if not job or job.organization_id != org_id:
        raise ValueError("invalid org/job")

    prov_name = (meeting_provider or "manual").lower()
    prov = get_meeting_provider(prov_name)
    meeting_url: str | None = manual_meeting_url
    cal_id: str | None = None
    err: str | None = None
    if create_calendar_event and meeting_url is None and prov_name in (
        "google_meet",
        "google",
        "gcal",
    ):
        result = await prov.create_meeting(
            title=f"Interview: {job.title or 'Role'}",
            start=slot_start,
            end=slot_end,
            timezone=tz,
            attendees_emails=[],
        )
        if result.success and result.meeting_url:
            meeting_url = result.meeting_url
            cal_id = result.calendar_event_id
        else:
            err = result.error_message
            fb = get_meeting_provider("manual")
            result2 = await fb.create_meeting(
                title="Interview",
                start=slot_start,
                end=slot_end,
                timezone=tz,
                attendees_emails=[],
            )
            meeting_url = result2.meeting_url
    elif meeting_url is None:
        m = get_meeting_provider("manual")
        r = await m.create_meeting(
            title="Interview",
            start=slot_start,
            end=slot_end,
            timezone=tz,
            attendees_emails=[],
        )
        meeting_url = r.meeting_url

    inv = Interview(
        id=uuid.uuid4(),
        application_id=application.id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        organization_id=org_id,
        interview_type=interview_type,
        status="scheduled",
        scheduled_start_time=slot_start,
        scheduled_end_time=slot_end,
        timezone=tz,
        meeting_provider=prov_name if meeting_url else "manual",
        meeting_url=meeting_url,
        calendar_event_id=cal_id,
        created_by_user_id=user.id,
    )
    db.add(inv)
    for uid in participant_user_ids:
        db.add(
            InterviewParticipant(
                id=uuid.uuid4(),
                interview_id=inv.id,
                user_id=uid,
                role="hr",
                attendance_status="invited",
            )
        )
    # Candidate as participant
    c = db.get(Candidate, application.candidate_id)
    if c and c.user_id:
        db.add(
            InterviewParticipant(
                id=uuid.uuid4(),
                interview_id=inv.id,
                user_id=c.user_id,
                role="candidate",
                attendance_status="invited",
            )
        )
    log_interview_action(
        db,
        actor_user_id=user.id,
        action="interview.scheduled",
        entity_id=inv.id,
        new_value={"err": err},
    )
    return inv, err
