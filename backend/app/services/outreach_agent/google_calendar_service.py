"""
PATHS Backend — Google Calendar service for outreach bookings.

Uses the HR's per-user OAuth access token (from ``google_oauth_service``)
to call:

  * freeBusy.query — to confirm a slot is still available
  * events.insert  — to create the interview event with a Meet link

The access token is fetched fresh on every call (with refresh-token
rotation) so we never persist a stale token.

Returns dataclasses so callers don't depend on httpx response shapes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.services.outreach_agent.google_oauth_service import (
    get_access_token,
)

logger = logging.getLogger(__name__)

_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"


@dataclass
class CalendarEventResult:
    success: bool
    event_id: str | None = None
    meeting_url: str | None = None
    html_link: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


def is_slot_free(
    db: Session,
    *,
    hr_user_id: UUID,
    start: datetime,
    end: datetime,
    timezone_name: str = "UTC",
    calendar_id: str = "primary",
) -> tuple[bool, str | None]:
    """Return (free, error). free=True when there is no conflicting busy block."""
    token = get_access_token(db, user_id=hr_user_id)
    if not token:
        return False, "google_not_connected"
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": timezone_name,
        "items": [{"id": calendar_id}],
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                _FREEBUSY_URL,
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
    except httpx.HTTPError as exc:
        return False, f"freebusy_http_error:{exc}"
    if r.status_code >= 400:
        return False, f"freebusy_failed:{r.text[:300]}"
    data = r.json() or {}
    busy = (data.get("calendars") or {}).get(calendar_id, {}).get("busy") or []
    return (not busy), None


def create_interview_event(
    db: Session,
    *,
    hr_user_id: UUID,
    title: str,
    description: str,
    start: datetime,
    end: datetime,
    timezone_name: str = "UTC",
    attendee_emails: list[str] | None = None,
    calendar_id: str = "primary",
) -> CalendarEventResult:
    """Create the Google Calendar event and return the Meet link."""
    token = get_access_token(db, user_id=hr_user_id)
    if not token:
        return CalendarEventResult(success=False, error="google_not_connected")

    body: dict[str, Any] = {
        "summary": title[:255],
        "description": description[:8000],
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
        "attendees": [{"email": e} for e in (attendee_emails or []) if e],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {"useDefault": True},
    }
    url = _EVENTS_URL.format(calendar_id=calendar_id)
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"conferenceDataVersion": 1, "sendUpdates": "all"},
                json=body,
            )
    except httpx.HTTPError as exc:
        return CalendarEventResult(success=False, error=f"events_http_error:{exc}")
    if r.status_code >= 400:
        return CalendarEventResult(
            success=False, error=f"events_failed:{r.text[:400]}",
        )
    event = r.json() or {}
    meet_link = None
    for ep in (event.get("conferenceData") or {}).get("entryPoints") or []:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            meet_link = ep.get("uri")
            break
    return CalendarEventResult(
        success=True,
        event_id=event.get("id"),
        meeting_url=meet_link,
        html_link=event.get("htmlLink"),
        raw=event,
    )


def cancel_event(
    db: Session,
    *,
    hr_user_id: UUID,
    event_id: str,
    calendar_id: str = "primary",
) -> tuple[bool, str | None]:
    token = get_access_token(db, user_id=hr_user_id)
    if not token:
        return False, "google_not_connected"
    url = (
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}"
        f"/events/{event_id}"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.delete(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        return False, f"delete_http_error:{exc}"
    if r.status_code not in (200, 204, 410):
        return False, f"delete_failed:{r.text[:300]}"
    return True, None


__all__ = [
    "CalendarEventResult",
    "cancel_event",
    "create_interview_event",
    "is_slot_free",
]
