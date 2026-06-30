"""LangGraph nodes for the Outreach Agent pipeline.

Pipeline:
    compose_emails_node
        -> send_emails_node
        -> track_sends_node

The service layer (outreach_service, gmail_service, outreach_agent) already
handles the heavy lifting.  These nodes orchestrate the flow across multiple
candidates for a single job, using the LangGraph state to hand data between
steps.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: Compose emails
# ---------------------------------------------------------------------------

def compose_emails_node(state: dict[str, Any]) -> dict[str, Any]:
    """For each candidate_id, compose a personalized outreach email via the
    LLM and persist an OutreachSession record in ``draft`` status.

    Returns ``composed_sessions`` (list of session dicts) and
    ``compose_errors`` (list of error strings for candidates that failed).
    """
    job_id_str = state["job_id"]
    org_id_str = state["organization_id"]
    hr_user_id_str = state["hr_user_id"]
    candidate_ids: list[str] = state.get("candidate_ids") or []

    if not candidate_ids:
        logger.warning("[OutreachCompose] No candidates to outreach")
        return {
            "composed_sessions": [],
            "compose_errors": ["no_candidates"],
            "status": "failed",
            "error": "No candidate IDs provided",
        }

    from app.db.models.candidate import Candidate
    from app.db.models.job import Job
    from app.services.outreach_agent.outreach_agent import generate_outreach_email
    from app.services.outreach_agent.outreach_service import (
        CreateSessionInput,
        create_session,
    )

    composed: list[dict[str, Any]] = []
    errors: list[str] = []

    db = SessionLocal()
    try:
        job: Job | None = db.get(Job, UUID(job_id_str))
        if job is None:
            return {
                "composed_sessions": [],
                "compose_errors": [f"job_not_found:{job_id_str}"],
                "status": "failed",
                "error": f"Job {job_id_str} not found",
            }

        for cand_id_str in candidate_ids:
            try:
                cand: Candidate | None = db.get(Candidate, UUID(cand_id_str))
                if cand is None:
                    errors.append(f"candidate_not_found:{cand_id_str}")
                    continue

                # Generate email via LLM
                generated = generate_outreach_email(
                    candidate=cand,
                    job=job,
                )

                # Persist session as draft
                expires = datetime.now(timezone.utc) + timedelta(days=7)
                inp = CreateSessionInput(
                    candidate_id=UUID(cand_id_str),
                    job_id=UUID(job_id_str),
                    organization_id=UUID(org_id_str),
                    hr_user_id=UUID(hr_user_id_str),
                    subject=generated.subject,
                    email_body=generated.body,
                    interview_type="mixed",
                    duration_minutes=30,
                    buffer_minutes=10,
                    timezone="UTC",
                    expires_at=expires,
                )
                result = create_session(db, inp)

                composed.append({
                    "session_id": result["session_id"],
                    "raw_token": result.get("raw_token"),
                    "candidate_id": cand_id_str,
                    "recipient_email": getattr(cand, "email", None),
                    "status": "draft",
                })

            except Exception as exc:  # noqa: BLE001
                logger.exception("[OutreachCompose] failed for candidate %s", cand_id_str)
                errors.append(f"compose_error:{cand_id_str}:{exc!s}")

    finally:
        db.close()

    logger.info(
        "[OutreachCompose] job=%s composed=%d errors=%d",
        job_id_str, len(composed), len(errors),
    )

    return {
        "composed_sessions": composed,
        "compose_errors": errors,
    }


# ---------------------------------------------------------------------------
# Node 2: Send emails
# ---------------------------------------------------------------------------

def send_emails_node(state: dict[str, Any]) -> dict[str, Any]:
    """Send each composed draft session via Gmail.

    Updates OutreachSession.status to ``sent`` or ``failed``.
    Returns ``sent_count``, ``failed_count``, ``session_results``.
    """
    composed: list[dict[str, Any]] = state.get("composed_sessions") or []
    hr_user_id_str = state["hr_user_id"]
    org_id_str = state["organization_id"]

    if not composed:
        return {"sent_count": 0, "failed_count": 0, "session_results": []}

    from app.db.models.outreach_agent import OutreachSession
    from app.services.outreach_agent.outreach_service import send_session

    results: list[dict[str, Any]] = []
    sent = 0
    failed = 0

    db = SessionLocal()
    try:
        for entry in composed:
            session_id = entry.get("session_id")
            cand_id = entry.get("candidate_id")
            raw_token = entry.get("raw_token")

            if not session_id or not raw_token:
                failed += 1
                results.append({
                    "session_id": session_id,
                    "candidate_id": cand_id,
                    "status": "failed",
                    "error": "missing_token",
                })
                continue

            try:
                send_result = send_session(
                    db=db,
                    raw_token=raw_token,
                    hr_user_id=UUID(hr_user_id_str),
                )
                if send_result.get("ok"):
                    sent += 1
                    results.append({
                        "session_id": session_id,
                        "candidate_id": cand_id,
                        "status": "sent",
                    })
                else:
                    failed += 1
                    results.append({
                        "session_id": session_id,
                        "candidate_id": cand_id,
                        "status": "failed",
                        "error": send_result.get("error", "send_failed"),
                    })
            except Exception as exc:  # noqa: BLE001
                logger.exception("[OutreachSend] failed for session %s", session_id)
                failed += 1
                results.append({
                    "session_id": session_id,
                    "candidate_id": cand_id,
                    "status": "failed",
                    "error": str(exc),
                })
    finally:
        db.close()

    logger.info(
        "[OutreachSend] sent=%d failed=%d",
        sent, failed,
    )

    return {
        "sent_count": sent,
        "failed_count": failed,
        "session_results": results,
    }


# ---------------------------------------------------------------------------
# Node 3: Track sends
# ---------------------------------------------------------------------------

def track_sends_node(state: dict[str, Any]) -> dict[str, Any]:
    """Post-send housekeeping:

    * Updates ScreeningResult.status = 'approved_for_outreach' for all
      successfully-sent candidates.
    * Appends an analytics_events row for the whole outreach batch.
    * Determines the final pipeline ``status`` (completed/partial/failed).
    """
    results: list[dict[str, Any]] = state.get("session_results") or []
    sent_count: int = state.get("sent_count", 0)
    failed_count: int = state.get("failed_count", 0)
    job_id_str = state["job_id"]
    org_id_str = state["organization_id"]

    sent_candidate_ids = [
        r["candidate_id"] for r in results if r.get("status") == "sent"
    ]

    analytics_event_id: str | None = None

    db = SessionLocal()
    try:
        # Update ScreeningResult status for sent candidates
        if sent_candidate_ids:
            from app.db.models.screening import ScreeningResult

            for cand_id_str in sent_candidate_ids:
                # Find the most recent result for this candidate + job
                row: ScreeningResult | None = (
                    db.query(ScreeningResult)
                    .filter(
                        ScreeningResult.candidate_id == UUID(cand_id_str),
                        ScreeningResult.job_id == UUID(job_id_str),
                    )
                    .order_by(ScreeningResult.created_at.desc())
                    .first()
                )
                if row and row.status != "approved_for_outreach":
                    row.status = "approved_for_outreach"
                    db.add(row)

        # Append analytics event
        from app.db.models.analytics_events import AnalyticsEvent

        event = AnalyticsEvent(
            org_id=UUID(org_id_str),
            entity_type="job",
            entity_id=UUID(job_id_str),
            event_type="outreach_batch_sent",
            payload={
                "sent_count": sent_count,
                "failed_count": failed_count,
                "candidate_count": len(results),
                "sent_candidates": sent_candidate_ids,
            },
        )
        db.add(event)
        db.flush()
        analytics_event_id = str(event.id)

        db.commit()
        logger.info(
            "[OutreachTrack] job=%s sent=%d failed=%d tracked candidates=%d",
            job_id_str, sent_count, failed_count, len(sent_candidate_ids),
        )

    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[OutreachTrack] DB update failed")
    finally:
        db.close()

    # Final status
    total = sent_count + failed_count
    if total == 0:
        final_status = "failed"
    elif failed_count == 0:
        final_status = "completed"
    elif sent_count > 0:
        final_status = "partial"
    else:
        final_status = "failed"

    return {
        "tracked": True,
        "analytics_event_id": analytics_event_id,
        "status": final_status,
        "error": None,
    }
