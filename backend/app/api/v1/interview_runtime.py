"""
PATHS Backend — Interview Intelligence runtime endpoints.

Companion to ``app/api/v1/interviews.py``. Adds the live runtime + report
flows requested in the Interview Agent brief without touching the
existing interview routes:

  POST /api/v1/interviews/sessions                  alias to create-draft
  GET  /api/v1/interviews/sessions/{id}             session detail
  POST /api/v1/interviews/sessions/{id}/answer      record one Q&A turn
  POST /api/v1/interviews/sessions/{id}/follow-up   generate one follow-up
  POST /api/v1/interviews/sessions/{id}/finish      mark completed
  POST /api/v1/interviews/sessions/{id}/evaluate    delegate to existing analyze
  GET  /api/v1/interviews/sessions/{id}/turns       live transcript
  GET  /api/v1/interviews/sessions/{id}/report      unified report JSON
  GET  /api/v1/interviews/sessions/{id}/report/pdf  PDF download

All endpoints reuse the existing 8 interview tables — no schema changes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.interview import (
    Interview,
    InterviewDecisionPacket,
    InterviewEvaluation,
    InterviewParticipant,
    InterviewSummary,
)
from app.db.models.job import Job
from app.db.models.user import User
from app.schemas.interview_runtime import (
    AnswerTurnIn,
    AnswerTurnOut,
    CreateInterviewSessionIn,
    CreateInterviewSessionOut,
    FollowUpRequest,
    FollowUpResponse,
    FinishInterviewResponse,
    InterviewReportOut,
    InterviewSessionDetail,
    SessionTurnsOut,
)
from app.services.interview import runtime_service
from app.services.interview.interview_service import (
    assert_application_in_org,
    build_candidate_context,
    build_job_context,
    get_interview_for_org,
    get_latest_job_match_score,
    mark_completed_if_analyzed,
    require_org_hr,
    run_full_analysis,
)
from app.services.interview.runtime_service import TurnInput
from app.utils.pdf_report import build_interview_report_pdf

logger = logging.getLogger(__name__)
settings = get_settings()


router = APIRouter(prefix="/interviews/sessions", tags=["Interview Runtime"])


# ── Helpers ──────────────────────────────────────────────────────────────


def _resolve_organization_id(user: User, body_org_id: UUID | None = None) -> UUID:
    if body_org_id is not None:
        return body_org_id
    org = next(
        (m for m in (user.memberships or []) if m.is_active),
        None,
    )
    if org is None:
        raise HTTPException(status_code=403, detail="No active organization membership.")
    return org.organization_id


def _ensure_application(
    db: Session,
    *,
    application_id: UUID | None,
    candidate_id: UUID | None,
    job_id: UUID | None,
    organization_id: UUID,
) -> Application:
    if application_id is not None:
        app = assert_application_in_org(db, application_id, organization_id)
        return app
    if candidate_id is None or job_id is None:
        raise HTTPException(
            status_code=400,
            detail="Provide application_id OR candidate_id+job_id.",
        )
    job = db.get(Job, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(status_code=400, detail="Job/organization mismatch.")
    app = db.execute(
        select(Application)
        .where(
            Application.candidate_id == candidate_id,
            Application.job_id == job_id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if app is None:
        # Create a minimal sourced application so the interview can be tracked.
        app = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            application_type="ai_interview",
            source_channel="interview_intelligence",
            current_stage_code="hr_interview",
            overall_status="active",
        )
        db.add(app)
        db.flush()
    return app


def _serialize_interview(inv: Interview) -> dict[str, Any]:
    return {
        "id": str(inv.id),
        "application_id": str(inv.application_id),
        "candidate_id": str(inv.candidate_id),
        "job_id": str(inv.job_id),
        "organization_id": str(inv.organization_id),
        "interview_type": inv.interview_type,
        "status": inv.status,
        "scheduled_start_time": inv.scheduled_start_time.isoformat() if inv.scheduled_start_time else None,
        "scheduled_end_time": inv.scheduled_end_time.isoformat() if inv.scheduled_end_time else None,
        "timezone": inv.timezone,
        "meeting_provider": inv.meeting_provider,
        "meeting_url": inv.meeting_url,
        "created_by_user_id": str(inv.created_by_user_id) if inv.created_by_user_id else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }


# ── Endpoints ────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=CreateInterviewSessionOut,
    status_code=201,
    summary="Create an Interview Intelligence session (alias of POST /interviews/).",
)
def create_session(
    body: CreateInterviewSessionIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    org_id = _resolve_organization_id(user, body.organization_id)
    require_org_hr(db, user, org_id)
    app = _ensure_application(
        db,
        application_id=body.application_id,
        candidate_id=body.candidate_id,
        job_id=body.job_id,
        organization_id=org_id,
    )
    interview = Interview(
        application_id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        organization_id=org_id,
        interview_type=(body.interview_type or "mixed"),
        status="in_progress",
        meeting_provider="ai",
        created_by_user_id=user.id,
    )
    db.add(interview)
    db.flush()
    db.add(
        InterviewParticipant(
            interview_id=interview.id,
            user_id=user.id,
            role="hr",
            attendance_status="invited",
        )
    )
    db.add(
        InterviewParticipant(
            interview_id=interview.id,
            user_id=None,
            role="candidate",
            attendance_status="invited",
        )
    )
    db.commit()
    return CreateInterviewSessionOut(
        session_id=interview.id,
        status=interview.status,
        candidate_id=interview.candidate_id,
        job_id=interview.job_id,
        application_id=interview.application_id,
    )


@router.get(
    "/{session_id}",
    response_model=InterviewSessionDetail,
)
def get_session(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    candidate = db.get(Candidate, inv.candidate_id) if inv.candidate_id else None
    job = db.get(Job, inv.job_id) if inv.job_id else None
    questions = runtime_service.get_questions_flat(db, interview_id=inv.id)
    turns, completed = runtime_service.list_turns(db, interview_id=inv.id)
    return InterviewSessionDetail(
        session=_serialize_interview(inv),
        candidate={
            "id": str(candidate.id) if candidate else None,
            "full_name": candidate.full_name if candidate else None,
            "current_title": candidate.current_title if candidate else None,
            "headline": candidate.headline if candidate else None,
            "skills": list(candidate.skills or []) if candidate else [],
            "summary": candidate.summary if candidate else None,
            "years_experience": candidate.years_experience if candidate else None,
        },
        job={
            "id": str(job.id) if job else None,
            "title": job.title if job else None,
            "summary": job.summary if job else None,
            "seniority_level": job.seniority_level if job else None,
            "requirements": job.requirements if job else None,
        },
        questions=questions,
        turns=[t.__dict__ for t in turns],
        completed=completed,
    )


@router.post(
    "/{session_id}/answer",
    response_model=AnswerTurnOut,
    summary="Record one Q&A turn (live runtime).",
)
def post_answer(
    session_id: UUID,
    body: AnswerTurnIn,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    try:
        turn = runtime_service.record_answer(
            db,
            interview_id=inv.id,
            turn=TurnInput(
                question=body.question,
                answer=body.answer,
                is_followup=bool(body.is_followup),
                parent_index=body.parent_index,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnswerTurnOut(**turn.__dict__)


@router.post(
    "/{session_id}/follow-up",
    response_model=FollowUpResponse,
    summary="Generate a single follow-up question for a previous turn.",
)
def post_follow_up(
    session_id: UUID,
    body: FollowUpRequest,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    try:
        question = runtime_service.generate_followup(
            db, interview_id=inv.id, parent_index=int(body.parent_index),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FollowUpResponse(question=question, parent_index=body.parent_index)


@router.post(
    "/{session_id}/finish",
    response_model=FinishInterviewResponse,
    summary="Mark the live interview completed.",
)
def post_finish(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    try:
        result = runtime_service.finalize_session(db, interview_id=inv.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(inv)
    return FinishInterviewResponse(
        ok=bool(result.get("ok")),
        status=inv.status,
        turn_count=int(result.get("turn_count") or 0),
        already_completed=bool(result.get("already_completed")),
    )


@router.post(
    "/{session_id}/evaluate",
    summary="Run the existing LangGraph analysis pipeline (eval + report + decision packet).",
)
async def post_evaluate(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)

    from app.db.models.interview import InterviewTranscript

    # Prefer the live AI-interview turns when present. Otherwise fall back to
    # any existing transcript (e.g. a recall.ai meeting recording), so the
    # report can be (re)generated for real meetings too — these have no
    # runtime "turns", which is why Re-evaluate used to silently 400.
    plain = runtime_service.render_plain_transcript(db, interview_id=inv.id)
    if plain.strip():
        db.add(
            InterviewTranscript(
                interview_id=inv.id,
                transcript_source="ai_interview_render",
                transcript_text=plain,
                language="en",
                quality_hint="high",
            )
        )
        db.commit()
    else:
        existing = db.execute(
            select(InterviewTranscript)
            .where(InterviewTranscript.interview_id == inv.id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No transcript yet. Record the meeting with the Note Taker "
                    "(or run the live AI interview) before evaluating."
                ),
            )

    try:
        result = await run_full_analysis(db, interview=inv)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[InterviewRuntime] run_full_analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail="analysis_failed") from exc

    # Surface a clean reason instead of returning a silent {"error": ...}
    # body that the UI rendered as "nothing happened".
    if isinstance(result, dict) and result.get("error"):
        msg = {
            "no_transcript": (
                "No transcript was found for this interview. Record or upload "
                "the meeting transcript first."
            ),
            "interview module disabled": (
                "Interview Intelligence is disabled on this server."
            ),
        }.get(str(result.get("error")), f"Analysis could not complete: {result.get('error')}")
        raise HTTPException(status_code=422, detail=msg)
    # Persist the analysis rows + the auto-promoted "completed" status. Without
    # this the report's Re-evaluate produced results that vanished on refresh.
    db.commit()
    return {
        "ok": True,
        "interview_id": str(inv.id),
        "status": inv.status,
        "decision_id": str(result.get("decision_id")) if result.get("decision_id") else None,
        "compliance": result.get("compliance") or {},
    }


@router.get(
    "/{session_id}/turns",
    response_model=SessionTurnsOut,
)
def get_turns(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    turns, completed = runtime_service.list_turns(db, interview_id=inv.id)
    return SessionTurnsOut(
        session_id=session_id,
        completed=completed,
        turns=[t.__dict__ for t in turns],
    )


_EVAL_TITLES = {
    "hr": "HR Evaluation",
    "technical": "Technical Evaluation",
    "behavioral": "Behavioral Evaluation",
    "mixed": "Interview Evaluation",
}


def _coalesce_list(*vals: Any) -> list[Any]:
    for v in vals:
        if isinstance(v, list) and v:
            return v
    return []


def _normalize_scorecard(ev: InterviewEvaluation, sj: dict[str, Any]) -> dict[str, Any]:
    """Map a recall.ai / interview-intelligence scorecard into the report shape.

    The analysis pipeline stores HR/technical scorecards with keys like
    ``overall_hr_score`` / ``overall_technical_score`` and per-dimension
    ``*_score`` fields, with strengths/weaknesses/evidence nested *inside*
    ``score_json``. The report reader historically expected a flat
    ``overall_score`` plus dedicated columns, so nothing rendered. This
    normalizes both worlds into one predictable entry.
    """
    etype = (ev.evaluation_type or "").lower()
    overall = sj.get("overall_score")
    if overall is None:
        overall = sj.get("overall_hr_score")
    if overall is None:
        overall = sj.get("overall_technical_score")

    sub_scores: dict[str, Any] = {}
    for key, val in sj.items():
        if not key.endswith("_score"):
            continue
        if key in ("overall_score", "overall_hr_score", "overall_technical_score"):
            continue
        if isinstance(val, (int, float)):
            sub_scores[key[:-6]] = val  # strip trailing "_score"

    skill_scores = sj.get("skill_scores") if isinstance(sj.get("skill_scores"), dict) else {}
    title = _EVAL_TITLES.get(
        etype, (f"{etype.title()} Evaluation" if etype else "Evaluation"),
    )
    recommendation = (
        sj.get("recommendation_from_hr_perspective")
        or sj.get("recommendation_from_technical_perspective")
        or sj.get("recommendation")
    )
    return {
        "evaluation_type": ev.evaluation_type,
        "title": title,
        "question": title,  # keeps the PDF heading meaningful
        "score": overall,  # 0–10 scale
        "overall_score": overall,
        "score_scale": 10,
        "sub_scores": sub_scores,
        "skill_scores": skill_scores,
        "strongest_skills": _coalesce_list(sj.get("strongest_skills")),
        "weakest_skills": _coalesce_list(sj.get("weakest_skills")),
        "strengths": _coalesce_list(sj.get("strengths"), ev.strengths_json),
        "weaknesses": _coalesce_list(sj.get("weaknesses"), ev.weaknesses_json),
        "risks": _coalesce_list(sj.get("risks")),
        "development_needs": _coalesce_list(sj.get("development_needs")),
        "evidence": sj.get("evidence") if sj.get("evidence") is not None else ev.evidence_json,
        "recommendation": recommendation,
        "confidence": ev.confidence,
    }


def _load_report_payload(
    db: Session, interview: Interview,
) -> dict[str, Any]:
    summary_row = db.execute(
        select(InterviewSummary)
        .where(InterviewSummary.interview_id == interview.id)
        .order_by(InterviewSummary.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    eval_rows = list(
        db.execute(
            select(InterviewEvaluation)
            .where(InterviewEvaluation.interview_id == interview.id)
            .order_by(InterviewEvaluation.created_at.desc())
        ).scalars().all()
    )
    decision_row = db.execute(
        select(InterviewDecisionPacket)
        .where(InterviewDecisionPacket.interview_id == interview.id)
        .order_by(InterviewDecisionPacket.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    summary_json = summary_row.summary_json if summary_row else None
    decision_json = (
        decision_row.decision_packet_json if decision_row else None
    ) or {}
    if decision_row is not None:
        decision_json = {
            **(decision_json or {}),
            "recommendation": decision_row.recommendation,
            "final_score": decision_row.final_score,
            "confidence": decision_row.confidence,
            "human_review_required": decision_row.human_review_required,
        }

    flat_evals: list[dict[str, Any]] = []
    for ev in eval_rows:
        score_json = ev.score_json if isinstance(ev.score_json, dict) else {}
        # Runtime (simulated) interviews store per-question entries inside
        # score_json; real-meeting analysis stores a single scorecard per type.
        per_q = score_json.get("question_evaluations")
        if isinstance(per_q, list) and per_q:
            for entry in per_q:
                if isinstance(entry, dict):
                    flat_evals.append({**entry, "evaluation_type": ev.evaluation_type})
            continue
        flat_evals.append(_normalize_scorecard(ev, score_json))

    return {
        "summary": summary_json or {},
        "evaluations": flat_evals,
        "decision_packet": decision_json or None,
    }


def _load_report_extras(db: Session, inv: Interview) -> dict[str, Any]:
    """Real-meeting enrichment for the report: the recall/uploaded transcript
    text, the HR's free-text notes, the human hiring decision, and recording
    metadata. Kept separate from the AI analysis so a report can show the
    human side even when no model analysis exists yet."""
    from app.db.models.interview import InterviewHumanDecision, InterviewTranscript
    from app.services.interview import recall_service

    # Transcript text — prefer a stored transcript row (recall download or an
    # ai_interview_render), then fall back to the raw recall JSON blob.
    transcript_text = ""
    tr = db.execute(
        select(InterviewTranscript)
        .where(InterviewTranscript.interview_id == inv.id)
        .order_by(InterviewTranscript.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if tr and (tr.transcript_text or "").strip():
        transcript_text = tr.transcript_text.strip()
    elif inv.recall_transcript_json:
        try:
            transcript_text = recall_service.transcript_to_text(
                inv.recall_transcript_json
            ).strip()
        except Exception:  # noqa: BLE001
            transcript_text = ""

    # Human hiring decision — latest one wins.
    hd_row = db.execute(
        select(InterviewHumanDecision)
        .where(InterviewHumanDecision.interview_id == inv.id)
        .order_by(InterviewHumanDecision.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    human_decision: dict[str, Any] | None = None
    if hd_row is not None:
        decided_by_name = None
        if hd_row.decided_by:
            u = db.get(User, hd_row.decided_by)
            if u is not None:
                decided_by_name = getattr(u, "full_name", None) or getattr(u, "email", None)
        human_decision = {
            "final_decision": hd_row.final_decision,
            "hr_notes": hd_row.hr_notes,
            "decided_by": decided_by_name,
            "decided_at": hd_row.created_at.isoformat() if hd_row.created_at else None,
        }

    recording = {
        "has_recording": bool(inv.recall_recording_id or inv.recall_bot_id),
        "recording_id": inv.recall_recording_id,
        "bot_id": inv.recall_bot_id,
        "status": inv.recall_status,
        "status_message": inv.recall_status_message,
        "meeting_url": inv.meeting_url,
        "transcript_available": bool(transcript_text),
    }
    return {
        "transcript_text": transcript_text or None,
        "hr_notes": (inv.hr_notes or "").strip() or None,
        "human_decision": human_decision,
        "recording": recording,
    }


@router.get(
    "/{session_id}/report",
    response_model=InterviewReportOut,
)
def get_report(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    payload = _load_report_payload(db, inv)
    extras = _load_report_extras(db, inv)
    turns, completed = runtime_service.list_turns(db, interview_id=inv.id)
    # Auto-complete: a finished, analyzed interview shouldn't linger as
    # "scheduled". A decision packet only exists once a transcript was present
    # and analysis ran, so its presence is a safe completion signal (and heals
    # interviews analyzed before this rule existed, the moment they're opened).
    if mark_completed_if_analyzed(inv, has_analysis=bool(payload.get("decision_packet"))):
        db.add(inv)
        db.commit()
    completed = completed or inv.status == "completed"
    candidate = db.get(Candidate, inv.candidate_id) if inv.candidate_id else None
    job = db.get(Job, inv.job_id) if inv.job_id else None
    return InterviewReportOut(
        session_id=session_id,
        completed=completed,
        interview_type=inv.interview_type,
        status=inv.status,
        candidate={
            "id": str(candidate.id) if candidate else None,
            "full_name": candidate.full_name if candidate else None,
            "current_title": candidate.current_title if candidate else None,
            "skills": list(candidate.skills or []) if candidate else [],
            "summary": candidate.summary if candidate else None,
            "years_experience": candidate.years_experience if candidate else None,
        },
        job={
            "id": str(job.id) if job else None,
            "title": job.title if job else None,
            "summary": job.summary if job else None,
            "seniority_level": job.seniority_level if job else None,
        },
        summary=payload["summary"],
        evaluations=payload["evaluations"],
        decision_packet=payload["decision_packet"],
        turns=[t.__dict__ for t in turns],
        transcript_text=extras["transcript_text"],
        hr_notes=extras["hr_notes"],
        human_decision=extras["human_decision"],
        recording=extras["recording"],
    )


@router.get("/{session_id}/recording")
def get_recording_url(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lazily resolve a playable video URL for the meeting recording.

    Kept out of the main report payload because it requires a live Recall
    API round-trip (and the signed URL is short-lived). The report page
    fetches this on demand when the user opens the Recording section.
    """
    from app.services.interview import recall_service

    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    video_url = None
    if inv.recall_bot_id:
        video_url = recall_service.get_recording_video_url(inv.recall_bot_id)
    return {
        "video_url": video_url,
        "status": inv.recall_status,
        "status_message": inv.recall_status_message,
        "has_recording": bool(inv.recall_recording_id or inv.recall_bot_id),
        "meeting_url": inv.meeting_url,
    }


@router.get(
    "/{session_id}/report/pdf",
    summary="Download a PDF version of the interview report.",
)
def get_report_pdf(
    session_id: UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    inv = db.get(Interview, session_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="interview_not_found")
    require_org_hr(db, user, inv.organization_id)
    payload = _load_report_payload(db, inv)
    extras = _load_report_extras(db, inv)
    turns, _ = runtime_service.list_turns(db, interview_id=inv.id)
    candidate = db.get(Candidate, inv.candidate_id) if inv.candidate_id else None
    job = db.get(Job, inv.job_id) if inv.job_id else None
    pdf_bytes = build_interview_report_pdf(
        candidate={
            "full_name": candidate.full_name if candidate else None,
            "current_title": candidate.current_title if candidate else None,
            "headline": candidate.headline if candidate else None,
            "skills": list(candidate.skills or []) if candidate else [],
            "years_experience": candidate.years_experience if candidate else None,
        },
        job={
            "title": job.title if job else None,
            "seniority_level": job.seniority_level if job else None,
        },
        interview={
            "interview_type": inv.interview_type,
            "status": inv.status,
        },
        summary=payload["summary"] or {},
        evaluations=payload["evaluations"] or [],
        decision_packet=payload["decision_packet"] or {},
        transcript_turns=[t.__dict__ for t in turns],
        hr_notes=extras["hr_notes"],
        human_decision=extras["human_decision"],
        transcript_text=extras["transcript_text"],
    )
    filename = (
        f"PATHS-Interview-Report-{(candidate.full_name if candidate else 'candidate').replace(' ','_')}-"
        f"{str(inv.id)[:8]}.pdf"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
