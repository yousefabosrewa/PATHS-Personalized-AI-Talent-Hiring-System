"""
PATHS Backend — Public scheduling endpoints (no auth).

The candidate uses these endpoints via their secure tokenized link:

  GET  /api/v1/schedule/{token}        — fetch slots + status (no auth)
  POST /api/v1/schedule/{token}/book   — confirm a slot (no auth)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.outreach_agent import (
    BookSlotRequest,
    BookSlotResponse,
    PublicScheduleResponse,
    PublicSlot,
)
from app.services.outreach_agent import outreach_service

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/schedule", tags=["Public scheduling"])


@router.get("/{token}", response_model=PublicScheduleResponse)
def public_view(token: str, db: Session = Depends(get_db)):
    if not token or len(token) > 256:
        raise HTTPException(status_code=400, detail="invalid_token")
    try:
        _, view = outreach_service.get_public_session_view(db, raw_token=token)
    except ValueError as exc:
        msg = str(exc)
        if msg in {"token_not_found", "token_expired", "session_cancelled"}:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    return PublicScheduleResponse(
        organization_name=view.organization_name,
        job_title=view.job_title,
        candidate_name=view.candidate_name,
        interview_type=view.interview_type,
        duration_minutes=view.duration_minutes,
        timezone=view.timezone,
        expires_at=view.expires_at,
        booked=view.booked,
        slots=[PublicSlot(**s) for s in view.slots],
        booking=view.booking,
    )


@router.post("/{token}/book", response_model=BookSlotResponse)
def public_book(
    token: str,
    body: BookSlotRequest,
    db: Session = Depends(get_db),
):
    if not token or len(token) > 256:
        raise HTTPException(status_code=400, detail="invalid_token")
    result = outreach_service.book_slot(
        db,
        raw_token=token,
        selected_start_iso=body.selected_start_time,
        selected_end_iso=body.selected_end_time,
    )
    return BookSlotResponse(
        ok=bool(result.get("ok")),
        error=result.get("error"),
        booking_id=result.get("booking_id"),
        selected_start_time=result.get("selected_start_time"),
        selected_end_time=result.get("selected_end_time"),
        google_meet_link=result.get("google_meet_link"),
        google_connected=bool(result.get("google_connected")),
    )
