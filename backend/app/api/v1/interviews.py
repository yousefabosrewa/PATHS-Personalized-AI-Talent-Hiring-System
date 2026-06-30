"""
Interview intelligence API (PATHS extension).

Mounted at ``/api/v1/interviews``. AI outputs are recommendations only;
final hiring decisions require an HR user via ``human-decision``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.interview import (
    Interview,
    InterviewDecisionPacket,
    InterviewEvaluation,
    InterviewHumanDecision,
    InterviewQuestionPack,
    InterviewSummary,
    InterviewTranscript,
)
from app.db.models.user import User
from app.schemas.interview import (
    ApproveInterviewQuestionsRequest,
    GenerateInterviewQuestionsRequest,
    InterviewAnalyzeResponse,
    InterviewAvailabilityRequest,
    InterviewAvailabilityResponse,
    InterviewCancelRequest,
    InterviewCreateStub,
    InterviewDecisionPacketOut,
    InterviewEvaluationOut,
    InterviewHumanDecisionOut,
    InterviewHumanDecisionRequest,
    InterviewRescheduleRequest,
    InterviewScheduleRequest,
    InterviewScheduleResponse,
    InterviewSummaryOut,
    InterviewTranscriptCreate,
    InterviewListOut,
    TimeSlotOut,
)
from app.services.interview.interview_audit import log_interview_action
from app.services.interview.availability import list_availability
from app.services.interview.interview_service import (
    NO_SHOW_RECOMMENDATION,
    assert_application_in_org,
    candidate_owns_application,
    generate_question_packs,
    get_interview_for_org,
    mark_completed_if_analyzed,
    mark_no_show_if_expired,
    require_org_hr,
    run_full_analysis,
    schedule_interview,
)
from app.services.interview.meeting_providers import get_meeting_provider

settings = get_settings()
router = APIRouter(prefix="/interviews", tags=["Interviews"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[InterviewListOut])
def list_interviews(
    org_id: uuid.UUID = Query(..., description="Organization scope"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List interviews for an organisation (most recently updated first)."""
    require_org_hr(db, current_user, org_id)
    rows = db.execute(
        select(Interview)
        .where(Interview.organization_id == org_id)
        .order_by(desc(Interview.updated_at), desc(Interview.created_at))
        .limit(limit),
    ).scalars().all()
    out: list[InterviewListOut] = []
    healed = False
    for inv in rows:
        cand = db.get(Candidate, inv.candidate_id)
        job = db.get(Job, inv.job_id)
        # Scheduled time passed and nobody ever joined → no_show + zero score
        # (cleared again if the interview is rescheduled).
        if mark_no_show_if_expired(db, inv):
            healed = True
        # Latest decision packet → inline performance snapshot for the list row.
        packet = db.execute(
            select(InterviewDecisionPacket)
            .where(InterviewDecisionPacket.interview_id == inv.id)
            .order_by(desc(InterviewDecisionPacket.created_at))
            .limit(1)
        ).scalars().first()
        # A decision packet only exists after a transcript + analysis, so a still
        # "scheduled" interview that has one is really done → promote it here so
        # the Scheduled/Completed tabs reflect reality without a separate action.
        if mark_completed_if_analyzed(inv, has_analysis=packet is not None):
            db.add(inv)
            healed = True
        out.append(
            InterviewListOut(
                interview_id=inv.id,
                application_id=inv.application_id,
                job_id=inv.job_id,
                candidate_id=inv.candidate_id,
                candidate_name=cand.full_name if cand else "Unknown",
                job_title=job.title if job else "Unknown",
                interview_type=inv.interview_type,
                status=inv.status,
                scheduled_start=inv.scheduled_start_time,
                meeting_url=inv.meeting_url,
                recommendation=packet.recommendation if packet else None,
                final_score=packet.final_score if packet else None,
                confidence=packet.confidence if packet else None,
            ),
        )
    if healed:
        db.commit()
    return out


def _parse_uuid(s: str, name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(s)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {name}",
        ) from exc


# ── Scheduling & availability ─────────────────────────────────────────


@router.post("/availability", response_model=InterviewAvailabilityResponse)
def post_availability(
    body: InterviewAvailabilityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, body.organization_id)
    slots_raw = list_availability(body.from_date, body.to_date, body.slot_minutes)
    slots = [
        TimeSlotOut(start=x["start"], end=x["end"], timezone=x["timezone"])
        for x in slots_raw
    ]
    return InterviewAvailabilityResponse(
        organization_id=body.organization_id,
        slots=slots,
    )


@router.post("/schedule", response_model=InterviewScheduleResponse)
async def post_schedule(
    body: InterviewScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, body.organization_id)
    app = assert_application_in_org(db, body.application_id, body.organization_id)
    if not settings.interview_intelligence_enabled:
        raise HTTPException(status_code=503, detail="Interview module disabled")
    try:
        inv, err = await schedule_interview(
            db,
            application=app,
            org_id=body.organization_id,
            user=current_user,
            interview_type=body.interview_type,
            slot_start=body.slot_start,
            slot_end=body.slot_end,
            tz=body.timezone,
            participant_user_ids=body.participant_user_ids,
            meeting_provider=body.meeting_provider,
            manual_meeting_url=body.manual_meeting_url,
            create_calendar_event=body.create_calendar_event,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    db.refresh(inv)
    # Notify the interviewers to review the prepared drafts BEFORE the interview:
    # technical interview → technical Qs + pre-analysis; HR → HR Qs + pre-analysis.
    _notify_hr_prep_drafts(db, inv)
    return InterviewScheduleResponse(
        interview_id=inv.id,
        status=inv.status,
        meeting_url=inv.meeting_url,
        meeting_provider=inv.meeting_provider,
        calendar_event_id=inv.calendar_event_id,
        message=err,
    )


def _notify_hr_prep_drafts(db: Session, inv) -> None:
    """Email the interviewers (and creator) the prepared drafts to review before
    the interview. HR/behavioural → HR question drafts + pre-analysis; technical
    → technical question drafts + pre-analysis; mixed → all three. Best-effort."""
    try:
        from app.db.models.candidate import Candidate
        from app.db.models.interview import InterviewParticipant
        from app.db.models.job import Job
        from app.services.decision_support.decision_support_service import deliver_email
        from app.services.preparation import get_preparation_drafts

        itype = (inv.interview_type or "mixed").lower()
        if itype == "hr":
            wanted, kind_label = ["pre_analysis", "hr_questions"], "HR / behavioural interview"
        elif itype == "technical":
            wanted, kind_label = ["pre_analysis", "technical_questions"], "technical interview"
        else:
            wanted = ["pre_analysis", "technical_questions", "hr_questions"]
            kind_label = "interview"

        drafts = get_preparation_drafts(
            db,
            organization_id=inv.organization_id,
            candidate_id=inv.candidate_id,
            job_id=inv.job_id,
        )
        cand = db.get(Candidate, inv.candidate_id) if inv.candidate_id else None
        job = db.get(Job, inv.job_id) if inv.job_id else None
        cand_name = (cand.full_name if cand else None) or "the candidate"

        labels = {
            "pre_analysis": "Candidate pre-analysis",
            "technical_questions": "Technical question drafts",
            "hr_questions": "HR / behavioural question drafts",
        }
        lines = [
            f"A {kind_label} has been scheduled for {cand_name}"
            + (f" — {job.title}" if job else "") + ".",
            "",
            "Please review the prepared drafts before the interview:",
        ]
        for w in wanted:
            d = drafts.get(w)
            lines.append("")
            if not d:
                lines.append(f"[{labels[w]}] — NOT prepared yet. Generate it in the candidate's Preparation tab.")
                continue
            content = d.get("content") or {}
            lines.append(f"[{labels[w]}]")
            if w == "pre_analysis":
                s = str(content.get("summary") or "").strip()
                if s:
                    lines.append(f"  {s}")
            else:
                qs = content.get("questions") if isinstance(content.get("questions"), list) else []
                if not qs:
                    lines.append("  (no questions in this draft — regenerate in the Preparation tab)")
                for i, q in enumerate(qs, 1):
                    qt = str(q.get("question") or "").strip() if isinstance(q, dict) else ""
                    if qt:
                        lines.append(f"  {i}. {qt}")
        lines += ["", "Open the candidate's Preparation tab to review and adjust before the interview."]
        body = "\n".join(lines)
        subject = f"Review interview prep — {cand_name} ({kind_label})"

        recipient_ids: set = set()
        for p in db.execute(
            select(InterviewParticipant).where(InterviewParticipant.interview_id == inv.id)
        ).scalars().all():
            uid = getattr(p, "user_id", None)
            if uid:
                recipient_ids.add(uid)
        if getattr(inv, "created_by_user_id", None):
            recipient_ids.add(inv.created_by_user_id)

        for uid in recipient_ids:
            u = db.get(User, uid)
            if u and getattr(u, "email", None):
                deliver_email(db, to=u.email, subject=subject, body=body, hr_user_id=uid)
    except Exception:  # noqa: BLE001
        logger.exception("[InterviewPrepNotify] failed to notify HR of prep drafts")


@router.post("/", status_code=201)
def create_interview_draft(
    body: InterviewCreateStub,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    require_org_hr(db, current_user, body.organization_id)
    app = assert_application_in_org(db, body.application_id, body.organization_id)
    inv = Interview(
        id=uuid.uuid4(),
        application_id=app.id,
        candidate_id=app.candidate_id,
        job_id=app.job_id,
        organization_id=body.organization_id,
        interview_type=body.interview_type,
        status="draft",
        created_by_user_id=current_user.id,
    )
    db.add(inv)
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.create_draft",
        entity_id=inv.id, new_value={},
    )
    db.commit()
    return {"interview_id": str(inv.id), "status": inv.status}


@router.patch("/{interview_id}/reschedule")
async def patch_reschedule(
    interview_id: str,
    body: InterviewRescheduleRequest,
    org_id: uuid.UUID = Query(..., description="Organization scope"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    prov = get_meeting_provider("google_meet")
    if inv.calendar_event_id:
        await prov.update_meeting(
            calendar_event_id=inv.calendar_event_id,
            start=body.new_start,
            end=body.new_end,
            timezone=body.timezone,
        )
    inv.scheduled_start_time = body.new_start
    inv.scheduled_end_time = body.new_end
    inv.timezone = body.timezone
    inv.status = "rescheduled"
    # Rescheduling forgives a no-show: drop the auto zero-score packet(s) so
    # the candidate is scored on the new meeting instead.
    db.execute(
        delete(InterviewDecisionPacket).where(
            InterviewDecisionPacket.interview_id == inv.id,
            InterviewDecisionPacket.recommendation == NO_SHOW_RECOMMENDATION,
        ),
        execution_options={"synchronize_session": False},
    )
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.reschedule",
        entity_id=inv.id, new_value={"start": body.new_start.isoformat()},
    )
    db.commit()
    return {"interview_id": str(inv.id), "status": inv.status}


@router.patch("/{interview_id}/cancel")
def patch_cancel(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    body: InterviewCancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    inv.status = "cancelled"
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.cancel",
        entity_id=inv.id, new_value={"reason": (body and body.reason) or None},
    )
    db.commit()
    return {"interview_id": str(inv.id), "status": inv.status}


# ── Questions ─────────────────────────────────────────────────────────


@router.post("/{interview_id}/generate-questions")
async def post_generate_questions(
    interview_id: str,
    body: GenerateInterviewQuestionsRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    if not settings.interview_intelligence_enabled:
        raise HTTPException(status_code=503, detail="Interview module disabled")
    packs = await generate_question_packs(
        db, inv, include_hr=body.include_hr, include_technical=body.include_technical,
        regenerate=body.regenerate,
    )
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.generate_questions",
        entity_id=inv.id, new_value={},
    )
    db.commit()
    return {"question_pack_ids": [str(p.id) for p in packs]}


@router.get("/{interview_id}/questions")
def get_questions(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    rows = db.execute(
        select(InterviewQuestionPack).where(InterviewQuestionPack.interview_id == inv.id),
    ).scalars().all()
    return {
        "interview_id": str(inv.id),
        "packs": [
            {
                "id": str(r.id),
                "question_pack_type": r.question_pack_type,
                "questions_json": r.questions_json,
                "approved_by_hr": r.approved_by_hr,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            }
            for r in rows
        ],
    }


@router.patch("/{interview_id}/questions/approve")
def patch_questions_approve(
    interview_id: str,
    body: ApproveInterviewQuestionsRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from datetime import timezone as dt_tz

    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    rows = db.execute(
        select(InterviewQuestionPack).where(InterviewQuestionPack.interview_id == inv.id),
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No question packs")
    for r in rows:
        r.approved_by_hr = body.approved
        r.approved_at = datetime.now(dt_tz.utc) if body.approved else None
        if body.edited_questions_json is not None:
            r.questions_json = body.edited_questions_json
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.questions_approve",
        entity_id=inv.id, new_value={"approved": body.approved},
    )
    db.commit()
    return {"ok": True}


# ── Transcript & analysis ─────────────────────────────────────────────


@router.post("/{interview_id}/transcript")
def post_transcript(
    interview_id: str,
    body: InterviewTranscriptCreate,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    tr = InterviewTranscript(
        id=uuid.uuid4(),
        interview_id=inv.id,
        transcript_text=body.transcript_text,
        transcript_source=body.transcript_source,
        language=body.language,
        quality_hint=body.quality_hint,
    )
    db.add(tr)
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.transcript_upload",
        entity_id=inv.id, new_value={"len": len(body.transcript_text)},
    )
    db.commit()
    return {"transcript_id": str(tr.id)}


@router.post("/{interview_id}/transcribe-audio")
async def post_transcribe_audio(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    get_interview_for_org(db, iid, org_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Audio transcription is not wired in this deployment; upload a text transcript instead.",
    )


@router.post("/{interview_id}/analyze", response_model=InterviewAnalyzeResponse)
async def post_analyze(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    if not settings.interview_intelligence_enabled:
        raise HTTPException(status_code=503, detail="Interview module disabled")
    try:
        result = await run_full_analysis(db, inv)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Defence in depth: any unexpected failure returns a clean JSON error
        # (with CORS headers) instead of an opaque "Failed to fetch".
        raise HTTPException(
            status_code=502,
            detail=f"Interview analysis failed: {exc}",
        ) from exc
    # INST.md §10 — never run fake analysis without a usable transcript.
    if result.get("error") == "no_transcript":
        raise HTTPException(
            status_code=422,
            detail=(
                "No interview transcript is available yet. Run the Note Taker "
                "and wait for the post-meeting transcript before running analysis."
            ),
        )
    if result.get("error"):
        err = str(result.get("error"))
        if "429" in err or "rate" in err.lower() or "too many requests" in err.lower():
            raise HTTPException(
                status_code=429,
                detail=(
                    "The AI model is rate-limited right now (free tier). "
                    "Please wait a moment and click Run Analysis again."
                ),
            )
        raise HTTPException(status_code=422, detail=err)
    # ``result`` holds ORM objects (InterviewSummary) + a UUID, which are not
    # JSON-serializable for the audit log's JSONB column. Log only a small,
    # serializable summary instead (the previous code crashed here with
    # "Object of type InterviewSummary is not JSON serializable", which the
    # browser saw as "Failed to fetch").
    decision_id = result.get("decision_id")
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.analyze",
        entity_id=inv.id,
        new_value={"decision_id": str(decision_id) if decision_id else None},
    )
    db.commit()
    summ = result.get("summary")
    summ_out = None
    if summ:
        db.refresh(summ)
        summ_out = InterviewSummaryOut(
            id=summ.id, summary_json=summ.summary_json, created_at=summ.created_at,
        )
    ev_hr = db.execute(
        select(InterviewEvaluation)
        .where(InterviewEvaluation.interview_id == inv.id, InterviewEvaluation.evaluation_type == "hr")
        .order_by(InterviewEvaluation.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    ev_t = db.execute(
        select(InterviewEvaluation)
        .where(InterviewEvaluation.interview_id == inv.id, InterviewEvaluation.evaluation_type == "technical")
        .order_by(InterviewEvaluation.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    de = db.execute(
        select(InterviewDecisionPacket)
        .where(InterviewDecisionPacket.interview_id == inv.id)
        .order_by(InterviewDecisionPacket.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    return InterviewAnalyzeResponse(
        interview_id=inv.id,
        summary=summ_out,
        hr_evaluation=InterviewEvaluationOut(
            id=ev_hr.id, evaluation_type=ev_hr.evaluation_type,
            score_json=ev_hr.score_json, recommendation=ev_hr.recommendation,
            confidence=ev_hr.confidence, created_at=ev_hr.created_at,
        ) if ev_hr else None,
        technical_evaluation=InterviewEvaluationOut(
            id=ev_t.id, evaluation_type=ev_t.evaluation_type,
            score_json=ev_t.score_json, recommendation=ev_t.recommendation,
            confidence=ev_t.confidence, created_at=ev_t.created_at,
        ) if ev_t else None,
        decision_packet=InterviewDecisionPacketOut(
            id=de.id, recommendation=de.recommendation, final_score=de.final_score,
            confidence=de.confidence, decision_packet_json=de.decision_packet_json,
            human_review_required=de.human_review_required, created_at=de.created_at,
        ) if de else None,
        compliance=result.get("compliance") or {},
    )


@router.get("/{interview_id}/summary")
def get_summary(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    row = db.execute(
        select(InterviewSummary)
        .where(InterviewSummary.interview_id == inv.id)
        .order_by(InterviewSummary.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No summary")
    return {"id": str(row.id), "summary_json": row.summary_json, "created_at": row.created_at}


@router.get("/{interview_id}/evaluation")
def get_evaluation(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    rows = db.execute(
        select(InterviewEvaluation).where(InterviewEvaluation.interview_id == inv.id),
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "evaluation_type": r.evaluation_type,
                "score_json": r.score_json,
                "recommendation": r.recommendation,
                "confidence": r.confidence,
            }
            for r in rows
        ],
    }


@router.get("/{interview_id}/decision-packet")
def get_decision_packet(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    row = db.execute(
        select(InterviewDecisionPacket)
        .where(InterviewDecisionPacket.interview_id == inv.id)
        .order_by(InterviewDecisionPacket.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No decision packet")
    return {
        "id": str(row.id),
        "recommendation": row.recommendation,
        "decision_packet_json": row.decision_packet_json,
        "human_review_required": row.human_review_required,
    }


# ── HR Notes (INST.md §8/§9) ──────────────────────────────────────────


@router.get("/{interview_id}/decision-state")
def get_decision_state(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Whether a human decision was already taken for this interview (PATHS.md §1).

    Used by the management UI to hide Proceed/Reject once the action is done.
    """
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    last = db.execute(
        select(InterviewHumanDecision)
        .where(InterviewHumanDecision.interview_id == inv.id)
        .order_by(desc(InterviewHumanDecision.created_at))
        .limit(1),
    ).scalar_one_or_none()
    return {
        "interview_id": str(inv.id),
        "status": inv.status,
        "decision_taken": last is not None or inv.status == "completed",
        "final_decision": last.final_decision if last else None,
        "candidate_id": str(inv.candidate_id),
    }


@router.get("/{interview_id}/hr-notes")
def get_hr_notes(
    interview_id: str,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the persisted HR Notes for an interview (HR only)."""
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    return {"interview_id": str(inv.id), "hr_notes": inv.hr_notes or ""}


@router.put("/{interview_id}/hr-notes")
def put_hr_notes(
    interview_id: str,
    body: dict,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Persist HR Notes for an interview (HR only)."""
    iid = _parse_uuid(interview_id)
    require_org_hr(db, current_user, org_id)
    inv = get_interview_for_org(db, iid, org_id)
    notes = body.get("hr_notes")
    inv.hr_notes = (notes or "").strip() or None
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.hr_notes_save",
        entity_id=inv.id, new_value={"len": len(inv.hr_notes or "")},
    )
    db.commit()
    return {"interview_id": str(inv.id), "hr_notes": inv.hr_notes or ""}


# ── Human decision (HR only) ──────────────────────────────────────────


@router.post("/{interview_id}/human-decision", response_model=InterviewHumanDecisionOut)
def post_human_decision(
    interview_id: str,
    body: InterviewHumanDecisionRequest,
    org_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    require_org_hr(
        db, current_user, org_id,
        allowed_roles=("org_admin", "recruiter", "hr", "hr_manager", "hiring_manager", "admin"),
    )
    inv = get_interview_for_org(db, iid, org_id)
    row = InterviewHumanDecision(
        id=uuid.uuid4(),
        interview_id=inv.id,
        decided_by=current_user.id,
        final_decision=body.final_decision,
        hr_notes=body.hr_notes,
        override_reason=body.override_reason,
    )
    db.add(row)
    # Recording a human decision concludes the interview — mark it completed
    # so it moves out of the "Scheduled" bucket and into "Completed".
    inv.status = "completed"
    log_interview_action(
        db, actor_user_id=current_user.id, action="interview.human_decision",
        entity_id=inv.id,
        new_value={
            "decision": body.final_decision,
            "override_reason": body.override_reason,
            "interview_status": inv.status,
        },
    )
    db.commit()
    db.refresh(row)
    return InterviewHumanDecisionOut(
        id=row.id,
        interview_id=inv.id,
        final_decision=row.final_decision,
        hr_notes=row.hr_notes,
        override_reason=row.override_reason,
        created_at=row.created_at,
        candidate_id=inv.candidate_id,
        application_id=inv.application_id,
        job_id=inv.job_id,
        interview_status=inv.status,
    )


# ── Candidate: own interview scheduling view (read-only link + slot confirm) ─


@router.get("/candidate/{interview_id}/meeting")
def candidate_meeting(
    interview_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    iid = _parse_uuid(interview_id)
    inv = db.get(Interview, iid)
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")
    cand = current_user.candidate_profile
    if not cand or inv.candidate_id != cand.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "interview_id": str(inv.id),
        "meeting_url": inv.meeting_url,
        "scheduled_start_time": inv.scheduled_start_time,
        "scheduled_end_time": inv.scheduled_end_time,
        "timezone": inv.timezone,
        "status": inv.status,
    }
