"""
PATHS Backend — Outreach orchestration service.

High-level operations used by the routers:
  * generate_email_for_session  — call OutreachAgent on cached candidate/job
  * create_session              — persist OutreachSession + windows
  * send_session                — replace placeholder, send via Gmail API
  * get_public_session_view     — public view by raw scheduling token
  * book_slot                   — confirm slot, create Calendar event,
                                   persist InterviewBooking
  * list_history                — outreach history per candidate

Each operation creates an audit_log row via the existing helper so the
full lifecycle is traceable without a duplicate event table.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.interview import Interview
from app.db.models.job import Job
from app.db.models.organization import Organization
from app.db.models.outreach_agent import (
    GoogleIntegration,
    InterviewBooking,
    OutreachAvailabilityWindow,
    OutreachSession,
)
from app.db.models.sync import CandidateJobMatch
from app.db.repositories import sync_status
from app.services.outreach_agent.availability_service import (
    AvailabilityWindowDTO,
    Slot,
    generate_slots,
)
from app.services.outreach_agent.google_calendar_service import (
    cancel_event,
    create_interview_event,
    is_slot_free,
)
from app.services.outreach_agent.gmail_service import send_email
from app.services.outreach_agent.outreach_agent import (
    GeneratedEmail,
    generate_outreach_email,
)
from app.services.outreach_agent.token_crypto import (
    constant_time_eq,
    hash_token,
    new_scheduling_token,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ── DTOs ─────────────────────────────────────────────────────────────────


@dataclass
class CreateSessionInput:
    candidate_id: UUID
    job_id: UUID | None
    organization_id: UUID
    hr_user_id: UUID
    subject: str
    email_body: str
    interview_type: str | None = None
    duration_minutes: int = 30
    buffer_minutes: int = 10
    timezone: str = "Africa/Cairo"
    expires_at: datetime | None = None
    availability: list[dict[str, Any]] | None = None
    recipient_email: str | None = None


@dataclass
class PublicSessionView:
    organization_name: str | None
    job_title: str | None
    hr_name: str | None
    candidate_name: str | None
    interview_type: str | None
    duration_minutes: int
    timezone: str
    expires_at: datetime | None
    booked: bool
    slots: list[dict[str, str]]
    booking: dict[str, Any] | None = None


# ── Audit helper (reuse existing audit_logs) ─────────────────────────────


def _audit(
    db: Session,
    *,
    action: str,
    session_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        sync_status.write_audit_log(
            db,
            action=action,
            entity_type="outreach_session",
            entity_id=str(session_id),
            metadata=metadata or {},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("[Outreach] audit log failed")
        db.rollback()


# ── High-level operations ───────────────────────────────────────────────


def generate_email_for_candidate(
    db: Session,
    *,
    candidate_id: UUID,
    job_id: UUID | None,
    organization_id: UUID,
    hr_user_id: UUID,
    hr_name: str | None,
    interview_type: str | None = None,
    is_final_offer: bool = False,
    extra_instructions: str | None = None,
) -> GeneratedEmail:
    cand = db.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")
    job = db.get(Job, job_id) if job_id else None
    org = db.get(Organization, organization_id)

    candidate_profile = {
        "full_name": cand.full_name,
        "current_title": cand.current_title,
        "headline": cand.headline,
        "skills": list(cand.skills or []),
        "summary": cand.summary,
        "years_experience": cand.years_experience,
        "location_text": cand.location_text,
    }
    job_details = (
        {
            "title": job.title,
            "summary": job.summary or job.description_text,
            "description_text": job.description_text,
            "seniority_level": job.seniority_level,
            "workplace_type": job.workplace_type or job.location_mode,
            "location_text": job.location_text,
        }
        if job is not None
        else {"title": None}
    )
    organization = (
        {"name": org.name, "industry": getattr(org, "industry", None)}
        if org is not None
        else {"name": None}
    )

    match_context: dict[str, Any] = {}
    if job_id:
        m = db.execute(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_id == candidate_id,
                CandidateJobMatch.job_id == job_id,
            )
            .order_by(CandidateJobMatch.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if m is not None:
            match_context = {
                "score": float(m.overall_score) if m.overall_score is not None else None,
                "matched_skills": (m.evidence or {}).get("matched_skills") or [],
                "strengths": (m.evidence or {}).get("strengths") or [],
            }

    return generate_outreach_email(
        candidate_profile=candidate_profile,
        job_details=job_details,
        organization=organization,
        hr_name=hr_name,
        interview_type=interview_type,
        match_context=match_context,
        is_final_offer=is_final_offer,
        disclose_ai_score=False,
        extra_instructions=extra_instructions,
    )


def create_session(
    db: Session, *, body: CreateSessionInput,
) -> tuple[OutreachSession, str]:
    cand = db.get(Candidate, body.candidate_id)
    if cand is None:
        raise ValueError("candidate_not_found")
    if not (body.recipient_email or cand.email):
        raise ValueError("candidate_has_no_email")

    raw_token, token_hash = new_scheduling_token()
    expires = body.expires_at or (
        datetime.now(timezone.utc) + timedelta(days=int(settings.outreach_token_ttl_days))
    )
    session = OutreachSession(
        candidate_id=body.candidate_id,
        job_id=body.job_id,
        hr_user_id=body.hr_user_id,
        organization_id=body.organization_id,
        token_hash=token_hash,
        status="draft",
        subject=body.subject[:1000] if body.subject else None,
        email_body=body.email_body,
        recipient_email=(body.recipient_email or cand.email),
        interview_type=body.interview_type,
        interview_duration_minutes=int(body.duration_minutes or 30),
        buffer_minutes=int(body.buffer_minutes or 10),
        timezone=body.timezone or settings.outreach_default_timezone,
        expires_at=expires,
    )
    db.add(session)
    db.flush()

    for w in body.availability or []:
        try:
            db.add(
                OutreachAvailabilityWindow(
                    outreach_session_id=session.id,
                    day_of_week=int(w.get("day_of_week", 0)),
                    start_time=str(w.get("start_time", "09:00")),
                    end_time=str(w.get("end_time", "17:00")),
                    timezone=str(w.get("timezone") or session.timezone),
                )
            )
        except Exception:  # noqa: BLE001
            logger.warning("[Outreach] skipping invalid availability window: %s", w)
    db.commit()

    _audit(
        db,
        action="outreach.created",
        session_id=session.id,
        metadata={
            "candidate_id": str(session.candidate_id),
            "job_id": str(session.job_id) if session.job_id else None,
            "interview_type": session.interview_type,
        },
    )
    return session, raw_token


def send_session(
    db: Session,
    *,
    session_id: UUID,
    raw_scheduling_link: str,
) -> dict[str, Any]:
    session = db.get(OutreachSession, session_id)
    if session is None:
        raise ValueError("session_not_found")
    if not session.recipient_email:
        raise ValueError("missing_recipient_email")
    if not session.hr_user_id:
        raise ValueError("missing_hr_user")
    body = (session.email_body or "").replace(
        "{{SCHEDULING_LINK}}", raw_scheduling_link,
    )

    result = send_email(
        db,
        hr_user_id=session.hr_user_id,
        to=session.recipient_email,
        subject=session.subject or "(no subject)",
        body=body,
    )
    if not result.success:
        session.status = "failed"
        session.last_error = result.error
        db.commit()
        _audit(
            db,
            action="outreach.send_failed",
            session_id=session.id,
            metadata={"error": result.error},
        )
        return {"ok": False, "error": result.error}

    session.status = "sent"
    session.sent_at = datetime.now(timezone.utc)
    session.last_error = None
    db.commit()
    _audit(
        db,
        action="outreach.sent",
        session_id=session.id,
        metadata={"gmail_message_id": result.message_id},
    )
    return {"ok": True, "gmail_message_id": result.message_id}


def get_public_session_view(
    db: Session, *, raw_token: str,
) -> tuple[OutreachSession, PublicSessionView]:
    token_hash = hash_token(raw_token)
    session = db.execute(
        select(OutreachSession).where(OutreachSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if session is None:
        raise ValueError("token_not_found")
    if session.expires_at and session.expires_at < datetime.now(timezone.utc):
        raise ValueError("token_expired")
    if session.status in {"cancelled"}:
        raise ValueError("session_cancelled")

    org = db.get(Organization, session.organization_id) if session.organization_id else None
    job = db.get(Job, session.job_id) if session.job_id else None
    cand = db.get(Candidate, session.candidate_id) if session.candidate_id else None
    booking = db.execute(
        select(InterviewBooking).where(
            InterviewBooking.outreach_session_id == session.id,
        ).limit(1)
    ).scalar_one_or_none()

    booked = booking is not None
    slots: list[dict[str, str]] = []
    if not booked:
        windows = list(
            db.execute(
                select(OutreachAvailabilityWindow).where(
                    OutreachAvailabilityWindow.outreach_session_id == session.id,
                )
            ).scalars().all()
        )
        dtos = [
            AvailabilityWindowDTO(
                day_of_week=w.day_of_week,
                start_time=w.start_time,
                end_time=w.end_time,
                timezone=w.timezone or session.timezone,
            )
            for w in windows
        ]
        # Subtract concurrent confirmed bookings for the same HR user.
        busy: list[tuple[datetime, datetime]] = []
        if session.hr_user_id:
            other_bookings = db.execute(
                select(InterviewBooking).where(
                    InterviewBooking.hr_user_id == session.hr_user_id,
                    InterviewBooking.status == "confirmed",
                )
            ).scalars().all()
            busy = [
                (b.selected_start_time, b.selected_end_time)
                for b in other_bookings
            ]
        computed = generate_slots(
            windows=dtos,
            duration_minutes=session.interview_duration_minutes,
            buffer_minutes=session.buffer_minutes,
            horizon_days=14,
            busy_intervals=busy,
            timezone_name=session.timezone,
        )
        slots = [s.to_dict() for s in computed]

    booking_payload = None
    if booking is not None:
        booking_payload = {
            "selected_start_time": booking.selected_start_time.isoformat(),
            "selected_end_time": booking.selected_end_time.isoformat(),
            "timezone": booking.timezone,
            "google_meet_link": booking.google_meet_link,
            "status": booking.status,
        }

    if session.status == "sent" and session.opened_at is None:
        session.opened_at = datetime.now(timezone.utc)
        db.commit()

    view = PublicSessionView(
        organization_name=org.name if org else None,
        job_title=job.title if job else None,
        hr_name=None,  # do not leak HR full name without context
        candidate_name=(cand.full_name if cand else None),
        interview_type=session.interview_type,
        duration_minutes=session.interview_duration_minutes,
        timezone=session.timezone,
        expires_at=session.expires_at,
        booked=booked,
        slots=slots,
        booking=booking_payload,
    )
    return session, view


def _mirror_booking_into_interviews(
    db: Session,
    *,
    session: OutreachSession,
    start: datetime,
    end: datetime,
    meeting_url: str | None,
    calendar_event_id: str | None,
    google_connected: bool,
) -> str:
    """Create (or update) an ``Interview`` row that mirrors a candidate
    self-booking confirmed via the public scheduling link.

    Why: the recruiter's ``/interviews`` page only reads the ``interviews``
    table. Without this mirror, a booking placed via the outreach scheduling
    link lives only in ``interview_bookings`` and is invisible there. We
    keep the booking row authoritative for the public link/audit and create
    a parallel "scheduled" Interview row for the in-app surface.

    Idempotent — if an Interview row already exists for this outreach
    session (matched by ``raw_calendar_payload.outreach_session_id``) it is
    updated in place rather than duplicated. Returns the Interview id.
    """
    # Find an Application for (candidate, job) on this org; create a minimal
    # "hr_interview" stage row if the candidate hadn't been shortlisted yet
    # (e.g. outreach was launched ad-hoc).
    app_row = db.execute(
        select(Application).where(
            Application.candidate_id == session.candidate_id,
            Application.job_id == session.job_id,
        ).limit(1)
    ).scalar_one_or_none()
    if app_row is None:
        app_row = Application(
            candidate_id=session.candidate_id,
            job_id=session.job_id,
            application_type="sourced",
            source_channel="outreach_self_booking",
            current_stage_code="hr_interview",
            overall_status="active",
        )
        db.add(app_row)
        db.flush()

    # Reuse an existing mirrored Interview if we already created one for
    # this outreach session — keeps the operation idempotent if the booking
    # endpoint is retried.
    existing = db.execute(
        select(Interview).where(
            Interview.application_id == app_row.id,
            Interview.candidate_id == session.candidate_id,
            Interview.job_id == session.job_id,
            Interview.organization_id == session.organization_id,
        ).order_by(Interview.created_at.desc()).limit(1)
    ).scalar_one_or_none()

    payload = {
        "outreach_session_id": str(session.id),
        "google_connected": google_connected,
        "mirrored_from": "outreach_self_booking",
        # Keep the recruiter-facing label too — the dashboard can still
        # show "HR Interview" even though the code field is canonicalised.
        "interview_type_label": (session.interview_type or "").strip() or None,
    }
    # The question-pack generator only branches on the three canonical
    # codes (hr/technical/mixed). Outreach historically stored a display
    # label like "HR Interview" here, which caused the generator to skip
    # everything and silently produce zero packs. Normalise on the way in.
    from app.services.interview.interview_service import _normalize_interview_type
    interview_type = _normalize_interview_type(session.interview_type)
    provider = "google_meet" if google_connected else ("manual" if meeting_url else None)

    if existing is not None:
        existing.status = "scheduled"
        existing.interview_type = interview_type
        existing.scheduled_start_time = start
        existing.scheduled_end_time = end
        existing.timezone = session.timezone
        existing.meeting_provider = provider
        existing.meeting_url = meeting_url
        existing.calendar_event_id = calendar_event_id
        existing.raw_calendar_payload = payload
        if session.hr_user_id is not None:
            existing.created_by_user_id = session.hr_user_id
        db.flush()
        return str(existing.id)

    inv = Interview(
        application_id=app_row.id,
        candidate_id=session.candidate_id,
        job_id=session.job_id,
        organization_id=session.organization_id,
        interview_type=interview_type,
        status="scheduled",
        scheduled_start_time=start,
        scheduled_end_time=end,
        timezone=session.timezone,
        meeting_provider=provider,
        meeting_url=meeting_url,
        calendar_event_id=calendar_event_id,
        raw_calendar_payload=payload,
        created_by_user_id=session.hr_user_id,
    )
    db.add(inv)
    db.flush()
    return str(inv.id)


def book_slot(
    db: Session,
    *,
    raw_token: str,
    selected_start_iso: str,
    selected_end_iso: str,
) -> dict[str, Any]:
    token_hash = hash_token(raw_token)
    session = db.execute(
        select(OutreachSession).where(OutreachSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if session is None:
        return {"ok": False, "error": "token_not_found"}
    if session.expires_at and session.expires_at < datetime.now(timezone.utc):
        return {"ok": False, "error": "token_expired"}
    existing = db.execute(
        select(InterviewBooking).where(
            InterviewBooking.outreach_session_id == session.id,
        ).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return {"ok": False, "error": "already_booked"}

    try:
        start = datetime.fromisoformat(selected_start_iso)
        end = datetime.fromisoformat(selected_end_iso)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_slot_format"}
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end <= start:
        return {"ok": False, "error": "invalid_slot_range"}

    if session.hr_user_id is not None:
        # Re-check the slot is still in one of the offered windows.
        windows = list(
            db.execute(
                select(OutreachAvailabilityWindow).where(
                    OutreachAvailabilityWindow.outreach_session_id == session.id,
                )
            ).scalars().all()
        )
        dtos = [
            AvailabilityWindowDTO(
                day_of_week=w.day_of_week,
                start_time=w.start_time,
                end_time=w.end_time,
                timezone=w.timezone or session.timezone,
            )
            for w in windows
        ]
        # Subtract other bookings.
        other_bookings = db.execute(
            select(InterviewBooking).where(
                InterviewBooking.hr_user_id == session.hr_user_id,
                InterviewBooking.status == "confirmed",
            )
        ).scalars().all()
        busy = [
            (b.selected_start_time, b.selected_end_time)
            for b in other_bookings
        ]
        valid_slots = generate_slots(
            windows=dtos,
            duration_minutes=session.interview_duration_minutes,
            buffer_minutes=session.buffer_minutes,
            horizon_days=14,
            busy_intervals=busy,
            timezone_name=session.timezone,
        )
        if not _slot_in_list(start, end, valid_slots):
            return {"ok": False, "error": "slot_not_available"}

    candidate = db.get(Candidate, session.candidate_id) if session.candidate_id else None
    candidate_email = candidate.email if candidate else None

    integ = (
        db.execute(
            select(GoogleIntegration).where(
                GoogleIntegration.user_id == session.hr_user_id,
            )
        ).scalar_one_or_none()
        if session.hr_user_id
        else None
    )
    google_connected = bool(integ and integ.refresh_token_encrypted)

    meet_link: str | None = None
    event_id: str | None = None
    error: str | None = None
    if google_connected:
        free, fb_err = is_slot_free(
            db,
            hr_user_id=session.hr_user_id,
            start=start,
            end=end,
            timezone_name=session.timezone,
        )
        if not free:
            return {
                "ok": False,
                "error": fb_err or "slot_not_available",
            }
        title = (
            f"PATHS Interview – {candidate.full_name if candidate else 'Candidate'}"
        )
        description = (
            (session.email_body or "")
            .replace("{{SCHEDULING_LINK}}", "")
            .strip()[:6000]
        )
        attendees = [e for e in [candidate_email] if e]
        cal_result = create_interview_event(
            db,
            hr_user_id=session.hr_user_id,
            title=title,
            description=description,
            start=start,
            end=end,
            timezone_name=session.timezone,
            attendee_emails=attendees,
        )
        if not cal_result.success:
            error = cal_result.error
            return {"ok": False, "error": error or "calendar_event_failed"}
        meet_link = cal_result.meeting_url
        event_id = cal_result.event_id

    booking = InterviewBooking(
        outreach_session_id=session.id,
        candidate_id=session.candidate_id,
        job_id=session.job_id,
        hr_user_id=session.hr_user_id,
        selected_start_time=start,
        selected_end_time=end,
        timezone=session.timezone,
        google_calendar_event_id=event_id,
        google_meet_link=meet_link,
        status="confirmed",
        meta_json={"google_connected": google_connected},
    )
    db.add(booking)
    session.status = "booked"
    session.booked_at = datetime.now(timezone.utc)

    # Mirror the booking into the canonical ``interviews`` table so the
    # recruiter's /interviews page (which only reads from ``interviews``)
    # surfaces every candidate-self-booked slot. Best-effort: a failure
    # here must not break the booking — we still want the InterviewBooking
    # row + Calendar event to land. Requires a job_id (Interview.job_id is
    # NOT NULL); if the session was created without one we skip mirroring.
    interview_id: str | None = None
    if session.job_id is not None and session.candidate_id is not None:
        try:
            interview_id = _mirror_booking_into_interviews(
                db,
                session=session,
                start=start,
                end=end,
                meeting_url=meet_link,
                calendar_event_id=event_id,
                google_connected=google_connected,
            )
        except Exception:  # noqa: BLE001 — never break the booking response
            logger.exception(
                "[Outreach] failed to mirror booking into interviews table",
            )

    db.commit()

    _audit(
        db,
        action="outreach.booked",
        session_id=session.id,
        metadata={
            "selected_start_time": start.isoformat(),
            "selected_end_time": end.isoformat(),
            "google_event_id": event_id,
            "google_connected": google_connected,
        },
    )
    return {
        "ok": True,
        "booking_id": str(booking.id),
        "selected_start_time": start.isoformat(),
        "selected_end_time": end.isoformat(),
        "google_meet_link": meet_link,
        "google_event_id": event_id,
        "google_connected": google_connected,
    }


def list_history(
    db: Session, *, candidate_id: UUID, organization_id: UUID,
) -> list[dict[str, Any]]:
    rows = list(
        db.execute(
            select(OutreachSession)
            .where(
                OutreachSession.candidate_id == candidate_id,
                OutreachSession.organization_id == organization_id,
            )
            .order_by(OutreachSession.created_at.desc())
            .limit(50)
        ).scalars().all()
    )
    out: list[dict[str, Any]] = []
    for s in rows:
        booking = db.execute(
            select(InterviewBooking).where(
                InterviewBooking.outreach_session_id == s.id,
            ).limit(1)
        ).scalar_one_or_none()
        out.append(
            {
                "id": str(s.id),
                "candidate_id": str(s.candidate_id),
                "job_id": str(s.job_id) if s.job_id else None,
                "status": s.status,
                "subject": s.subject,
                "interview_type": s.interview_type,
                "sent_at": s.sent_at.isoformat() if s.sent_at else None,
                "booked_at": s.booked_at.isoformat() if s.booked_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "last_error": s.last_error,
                "booking": {
                    "selected_start_time": booking.selected_start_time.isoformat(),
                    "selected_end_time": booking.selected_end_time.isoformat(),
                    "google_meet_link": booking.google_meet_link,
                } if booking else None,
            }
        )
    return out


def _slot_in_list(start: datetime, end: datetime, slots: list[Slot]) -> bool:
    target_start = start.astimezone(timezone.utc)
    target_end = end.astimezone(timezone.utc)
    for s in slots:
        if (
            s.start.astimezone(timezone.utc) == target_start
            and s.end.astimezone(timezone.utc) == target_end
        ):
            return True
    return False


__all__ = [
    "CreateSessionInput",
    "PublicSessionView",
    "book_slot",
    "create_session",
    "generate_email_for_candidate",
    "get_public_session_view",
    "list_history",
    "send_session",
]
