"""
PATHS Backend — Recall.ai notetaker endpoints + webhook receiver.

Routes (all mounted under ``/api/v1``):

  PUT  /interviews/{id}/recall/recording-mode
       HR picks "post_meeting" or "real_time" before the meeting starts.
       Idempotent — can be flipped until the bot is dispatched.

  POST /interviews/{id}/recall/start
       Dispatches a Recall.ai bot to the meeting URL using the chosen
       mode. Requires the interview to have a meeting_url and a mode.

  POST /interviews/{id}/recall/stop
       Tells the active bot to leave the call.

  GET  /interviews/{id}/recall/transcript
       Returns the persisted transcript JSON + a flat text fallback.

  GET  /interviews/{id}/recall/stream
       Server-Sent Events stream of transcript chunks for real-time mode.
       The webhook receiver appends chunks to an in-memory queue per
       interview; this endpoint drains them as they arrive.

  POST /webhooks/recall
       Inbound webhook from Recall.ai. Verifies the Svix signature,
       routes ``bot.status_change``, ``recording.done``, ``transcript.done``,
       ``transcript.data``, and ``transcript.partial_data`` events.

No new DB tables — everything lives on the existing ``interviews`` row
(see ``app.db.models.interview.Interview.recall_*`` columns).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.db.models.interview import Interview, InterviewTranscript
from app.db.models.user import User
from app.services.interview import recall_service
from app.services.interview.interview_service import (
    get_interview_for_org,
    require_org_hr,
)

logger = logging.getLogger(__name__)
settings = get_settings()


router = APIRouter(prefix="/interviews", tags=["Interview · Recall.ai"])
webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ── In-memory per-interview SSE queues ───────────────────────────────────
# A real deployment would use Redis pub/sub; for a single-process backend
# this is sufficient and avoids a new dependency. The webhook receiver
# pushes chunks onto these queues and the SSE endpoint drains them.

_LIVE_QUEUES: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


def _broadcast_chunk(interview_id: uuid.UUID | str, chunk: dict[str, Any]) -> None:
    """Fan-out a transcript chunk to every SSE listener for this interview."""
    key = str(interview_id)
    dead: list[asyncio.Queue[dict[str, Any]]] = []
    for q in _LIVE_QUEUES.get(key, []):
        try:
            q.put_nowait(chunk)
        except asyncio.QueueFull:  # pragma: no cover
            dead.append(q)
    if dead:
        _LIVE_QUEUES[key] = [q for q in _LIVE_QUEUES[key] if q not in dead]


# ── Schemas ──────────────────────────────────────────────────────────────


class RecordingModeBody(BaseModel):
    mode: str = Field(..., description='"post_meeting" | "real_time"')


class RecallStateOut(BaseModel):
    interview_id: uuid.UUID
    recording_mode: str | None = None
    bot_id: str | None = None
    recording_id: str | None = None
    transcript_id: str | None = None
    status: str | None = None
    status_message: str | None = None
    transcript_available: bool = False
    transcript_path: str | None = None
    configured: bool = False


class RecallTranscriptOut(BaseModel):
    interview_id: uuid.UUID
    status: str | None = None
    transcript_json: Any | None = None
    transcript_text: str = ""
    transcript_path: str | None = None
    updated_at: datetime | None = None


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize_state(inv: Interview) -> RecallStateOut:
    return RecallStateOut(
        interview_id=inv.id,
        recording_mode=inv.recall_recording_mode,
        bot_id=inv.recall_bot_id,
        recording_id=inv.recall_recording_id,
        transcript_id=inv.recall_transcript_id,
        status=inv.recall_status,
        status_message=inv.recall_status_message,
        transcript_available=bool(inv.recall_transcript_json),
        transcript_path=inv.recall_transcript_path,
        configured=recall_service.is_configured(),
    )


def _require_configured() -> None:
    if not recall_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Recall.ai is not configured. Set RECALL_API_KEY in "
                "backend/.env and restart the backend."
            ),
        )


def _interview_for_hr(
    db: Session, user: User, interview_id: uuid.UUID,
) -> Interview:
    inv = db.get(Interview, interview_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    require_org_hr(db, user, inv.organization_id)
    return inv


def _transcripts_dir() -> str:
    out = settings.recall_transcripts_dir or "./uploads/transcripts"
    os.makedirs(out, exist_ok=True)
    return out


def _persist_transcript(
    inv: Interview, payload: Any, *, fmt: str = "final",
) -> str:
    """Write the transcript JSON to disk and return the path."""
    out_dir = _transcripts_dir()
    fname = f"{inv.id}__{fmt}.json"
    path = os.path.join(out_dir, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("[Recall] failed to write transcript to disk: %s", exc)
        return inv.recall_transcript_path or ""
    return path


def _mirror_into_interview_transcripts(
    db: Session, inv: Interview, payload: Any,
) -> None:
    """Save the flattened text into ``interview_transcripts`` so the AI
    Analysis pipeline (which reads from that table) picks up the Recall
    transcript without an extra "Save Transcript" click.

    Idempotent: if a Recall-sourced row already exists for this interview
    we overwrite its text; otherwise we insert a new row.
    """
    text = recall_service.transcript_to_text(payload)
    if not text.strip():
        return
    existing = db.execute(
        select(InterviewTranscript)
        .where(
            InterviewTranscript.interview_id == inv.id,
            InterviewTranscript.transcript_source == "recall_ai",
        )
        .order_by(InterviewTranscript.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()
    if existing is not None:
        existing.transcript_text = text
        existing.quality_hint = (
            "low" if len(text) < 200 else "medium" if len(text) < 2000 else "high"
        )
    else:
        db.add(
            InterviewTranscript(
                interview_id=inv.id,
                transcript_text=text,
                transcript_source="recall_ai",
                language=None,
                quality_hint=(
                    "low" if len(text) < 200
                    else "medium" if len(text) < 2000
                    else "high"
                ),
            ),
        )


# ── HR-facing endpoints ──────────────────────────────────────────────────


@router.get(
    "/{interview_id}/recall/state",
    response_model=RecallStateOut,
    summary="Read the current Recall bot state for an interview.",
)
def get_state(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallStateOut:
    return _serialize_state(_interview_for_hr(db, user, interview_id))


@router.put(
    "/{interview_id}/recall/recording-mode",
    response_model=RecallStateOut,
    summary="HR picks the recording mode before the meeting starts.",
)
def set_recording_mode(
    interview_id: uuid.UUID,
    body: RecordingModeBody,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallStateOut:
    inv = _interview_for_hr(db, user, interview_id)
    mode = (body.mode or "").strip().lower()
    if mode not in recall_service.VALID_RECORDING_MODES:
        raise HTTPException(
            status_code=400,
            detail=(
                "mode must be one of: "
                + ", ".join(recall_service.VALID_RECORDING_MODES)
            ),
        )
    # Cannot change the mode once a bot is in flight — operator must stop
    # the bot first to avoid the recording mid-stream confusion.
    if inv.recall_bot_id and inv.recall_status not in (None, "failed", "cancelled", "done"):
        raise HTTPException(
            status_code=409,
            detail="A bot is already running for this interview; stop it before changing the mode.",
        )
    inv.recall_recording_mode = mode
    if not inv.recall_status:
        inv.recall_status = "pending"
    db.commit()
    db.refresh(inv)
    return _serialize_state(inv)


@router.post(
    "/{interview_id}/recall/start",
    response_model=RecallStateOut,
    summary="Dispatch a Recall.ai bot to the interview's meeting URL.",
)
def start_bot(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallStateOut:
    _require_configured()
    inv = _interview_for_hr(db, user, interview_id)
    if not inv.meeting_url:
        raise HTTPException(
            status_code=400,
            detail="Interview has no meeting_url to send the bot to.",
        )
    if not inv.recall_recording_mode:
        raise HTTPException(
            status_code=400,
            detail="Pick a recording mode (post_meeting | real_time) first.",
        )
    if inv.recall_bot_id and inv.recall_status in (
        "joining", "in_call", "recording", "in_waiting_room",
    ):
        raise HTTPException(
            status_code=409,
            detail="A bot is already in this call. Stop it first if you want to restart.",
        )

    real_time = inv.recall_recording_mode == recall_service.RECORDING_MODE_REAL_TIME
    public_base = (settings.recall_public_webhook_url or "").rstrip("/")
    webhook_url = (
        f"{public_base}/api/v1/webhooks/recall" if public_base else None
    )

    try:
        result = recall_service.create_bot(
            meeting_url=inv.meeting_url,
            bot_name=settings.recall_bot_name,
            real_time_transcript=real_time,
            real_time_endpoint=webhook_url,
            metadata={
                "interview_id": str(inv.id),
                "organization_id": str(inv.organization_id),
                "candidate_id": str(inv.candidate_id),
                "job_id": str(inv.job_id),
                "recording_mode": inv.recall_recording_mode,
            },
        )
    except recall_service.RecallAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Recall.ai rejected the bot request: {exc}",
        ) from exc

    inv.recall_bot_id = str(result.get("id") or result.get("bot_id") or "") or None
    raw_status = result.get("status_changes") or result.get("status") or "joining"
    inv.recall_status = recall_service.normalize_status(
        raw_status[-1] if isinstance(raw_status, list) and raw_status else raw_status
    )
    inv.recall_status_message = "Bot dispatched."
    db.commit()
    db.refresh(inv)
    return _serialize_state(inv)


@router.post(
    "/{interview_id}/recall/stop",
    response_model=RecallStateOut,
    summary="Tell the bot to leave the meeting.",
)
def stop_bot(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallStateOut:
    _require_configured()
    inv = _interview_for_hr(db, user, interview_id)
    if not inv.recall_bot_id:
        raise HTTPException(status_code=404, detail="No bot is running for this interview.")
    already_left = False
    try:
        recall_service.stop_bot(inv.recall_bot_id)
    except recall_service.RecallAPIError as exc:
        # Recall returns 404 (bot gone) or 400 (bot not in a call it can
        # leave) when the meeting already ended and the bot left on its own.
        # Both are benign no-ops for "Stop" — not errors to surface.
        if exc.status_code not in (400, 404):
            raise HTTPException(
                status_code=502,
                detail=f"Recall.ai stop_bot failed: {exc}",
            ) from exc
        already_left = True

    # Don't clobber a recording/transcript status the webhook may already have
    # set (the meeting ending triggers recording_done → transcript).
    if inv.recall_status not in ("done", "recording_done", "transcribing"):
        inv.recall_status = "cancelled"
    inv.recall_status_message = (
        "Bot already left the meeting (it had already ended)."
        if already_left
        else "Stop requested by HR."
    )
    db.commit()
    db.refresh(inv)
    return _serialize_state(inv)


@router.post(
    "/{interview_id}/recall/sync",
    response_model=RecallStateOut,
    summary="Pull the latest bot / recording / transcript state from Recall.ai and persist it.",
)
def sync_bot_state(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallStateOut:
    """Manual sync for deployments where RECALL_PUBLIC_WEBHOOK_URL is blank.

    The client calls this after the meeting ends to fetch the current bot
    status, kick off transcription if the recording is ready, and download
    the finished transcript — all in one request.  Idempotent: calling it
    multiple times is safe.
    """
    _require_configured()
    inv = _interview_for_hr(db, user, interview_id)
    if not inv.recall_bot_id:
        raise HTTPException(status_code=404, detail="No bot associated with this interview.")

    # ── Step 1: refresh bot status ────────────────────────────────────────
    try:
        bot = recall_service.get_bot(inv.recall_bot_id)
    except recall_service.RecallAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Recall.ai get_bot failed: {exc}") from exc

    status_changes = bot.get("status_changes") or []
    latest_status = (
        recall_service.normalize_status(status_changes[-1])
        if status_changes
        else recall_service.normalize_status(bot.get("status"))
    )
    inv.recall_status = latest_status

    # Grab recording id if Recall attached it to the bot object.
    recordings = bot.get("recordings") or []
    if recordings and not inv.recall_recording_id:
        inv.recall_recording_id = str(recordings[0].get("id") or "") or inv.recall_recording_id

    # ── Step 2: if bot is done + recording exists → request transcript ────
    bot_done = latest_status in ("done", "call_ended", "recording_done", "fatal", "error")
    if bot_done and inv.recall_recording_id and not inv.recall_transcript_id:
        try:
            t = recall_service.create_async_transcript(inv.recall_recording_id)
            inv.recall_transcript_id = str(t.get("id") or "") or None
            inv.recall_status = "recording_done"
            inv.recall_status_message = "Transcription requested."
        except recall_service.RecallAPIError as exc:
            inv.recall_status_message = f"create_transcript failed: {exc}"

    # ── Step 3: if transcript id exists → try to download it ─────────────
    if inv.recall_transcript_id and not inv.recall_transcript_json:
        try:
            meta = recall_service.get_transcript(inv.recall_transcript_id)
            # Recall returns ``status`` as an object: { code, sub_code,
            # updated_at }.  Tolerate both that and a flat string for
            # forward-compat with old responses.
            raw_status = meta.get("status")
            if isinstance(raw_status, dict):
                t_code = str(raw_status.get("code") or "").lower()
            else:
                t_code = str(raw_status or "").lower()
            # Recall uses "done" (sometimes "completed" in older payloads) to
            # signal the artifact is ready.  Accept either.
            is_ready = t_code in ("done", "completed", "ready")
            # Some shapes ship the download URL at root, some under data.
            dl = (
                meta.get("download_url")
                or (meta.get("data") or {}).get("download_url")
                or (meta.get("data") or {}).get("transcript_url")
            )
            if is_ready or dl:
                if dl:
                    payload: Any = recall_service.download_transcript_payload(dl)
                else:
                    payload = meta
                inv.recall_transcript_json = payload
                inv.recall_transcript_path = _persist_transcript(inv, payload, fmt="final")
                # Mirror into interview_transcripts so AI Analysis can find it.
                _mirror_into_interview_transcripts(db, inv, payload)
                inv.recall_status = "done"
                inv.recall_status_message = "Transcript ready."
            else:
                inv.recall_status_message = (
                    f"Transcript still processing ({t_code or 'unknown'}) — "
                    "wait a minute and click Sync again."
                )
        except recall_service.RecallAPIError as exc:
            inv.recall_status_message = f"transcript fetch failed: {exc}"

    db.commit()
    db.refresh(inv)
    return _serialize_state(inv)


@router.get(
    "/{interview_id}/recall/transcript",
    response_model=RecallTranscriptOut,
    summary="Get the persisted transcript JSON for an interview.",
)
def get_transcript(
    interview_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> RecallTranscriptOut:
    inv = _interview_for_hr(db, user, interview_id)
    payload = inv.recall_transcript_json
    return RecallTranscriptOut(
        interview_id=inv.id,
        status=inv.recall_status,
        transcript_json=payload,
        transcript_text=recall_service.transcript_to_text(payload),
        transcript_path=inv.recall_transcript_path,
        updated_at=inv.updated_at,
    )


@router.get(
    "/{interview_id}/recall/stream",
    summary="Server-Sent Events stream of real-time transcript chunks.",
)
async def stream_transcript(
    interview_id: uuid.UUID,
    request: Request,
    token: str | None = Query(default=None, description="Auth token in query (EventSource cannot set headers)"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # EventSource can't send Authorization headers, so we let the client
    # pass the JWT as a query string. Validate it via the same dependency
    # the rest of the API uses.
    from app.core.security import decode_access_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")

    inv = _interview_for_hr(db, user, interview_id)

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1024)
    _LIVE_QUEUES[str(inv.id)].append(queue)

    async def event_source() -> AsyncIterator[bytes]:
        # First message replays any chunks already persisted so a
        # late-joining browser still sees the start of the conversation.
        if isinstance(inv.recall_transcript_json, list):
            yield (
                f"event: replay\ndata: "
                f"{json.dumps(inv.recall_transcript_json, ensure_ascii=False)}\n\n"
            ).encode("utf-8")
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=15.0)
                    payload_str = json.dumps(chunk, ensure_ascii=False)
                    yield f"event: transcript\ndata: {payload_str}\n\n".encode("utf-8")
                except asyncio.TimeoutError:
                    # Keep-alive comment so proxies don't time the stream out.
                    yield b": keep-alive\n\n"
        finally:
            try:
                _LIVE_QUEUES[str(inv.id)].remove(queue)
            except ValueError:
                pass

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ── Webhook receiver ─────────────────────────────────────────────────────


@webhook_router.post(
    "/recall",
    summary="Inbound Recall.ai webhook (bot status, recording done, transcript events).",
)
async def recall_webhook(
    request: Request,
    db: Session = Depends(get_db),
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
) -> dict[str, Any]:
    raw = await request.body()
    if not recall_service.verify_webhook_signature(
        payload=raw,
        svix_id=svix_id or "",
        svix_timestamp=svix_timestamp or "",
        svix_signature=svix_signature or "",
    ):
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        event = json.loads(raw.decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"bad_json: {exc}") from exc

    event_type = str(event.get("event") or "").strip().lower()
    data = event.get("data") or {}
    bot = (data.get("bot") or {}) if isinstance(data, dict) else {}
    recording = (data.get("recording") or {}) if isinstance(data, dict) else {}
    transcript = (data.get("transcript") or {}) if isinstance(data, dict) else {}

    bot_id = str(bot.get("id") or "") or None
    if not bot_id:
        logger.info("[Recall] webhook %s without bot.id — ignoring", event_type)
        return {"ok": True, "ignored": "no_bot_id"}

    inv = db.execute(
        select(Interview).where(Interview.recall_bot_id == bot_id).limit(1)
    ).scalar_one_or_none()
    if inv is None:
        logger.info("[Recall] webhook %s for unknown bot_id %s", event_type, bot_id)
        return {"ok": True, "ignored": "unknown_bot"}

    if event_type in ("bot.status_change", "bot.joining_call", "bot.in_call_recording", "bot.done"):
        new_status = recall_service.normalize_status(
            data.get("data") or data.get("status") or event_type.split(".")[-1]
        )
        inv.recall_status = new_status
        inv.recall_status_message = (data.get("data") or {}).get("sub_code") if isinstance(data.get("data"), dict) else None

    elif event_type == "recording.done":
        inv.recall_recording_id = str(recording.get("id") or "") or inv.recall_recording_id
        inv.recall_status = "recording_done"
        if inv.recall_recording_mode == recall_service.RECORDING_MODE_POST:
            # Kick off async transcription now that the recording exists.
            try:
                t = recall_service.create_async_transcript(inv.recall_recording_id)
                inv.recall_transcript_id = str(t.get("id") or "") or inv.recall_transcript_id
                inv.recall_status_message = "Transcription requested."
            except recall_service.RecallAPIError as exc:
                inv.recall_status = "failed"
                inv.recall_status_message = f"create_transcript failed: {exc}"

    elif event_type == "transcript.done":
        tid = str(transcript.get("id") or "") or inv.recall_transcript_id
        if tid:
            inv.recall_transcript_id = tid
            try:
                meta = recall_service.get_transcript(tid)
                # Recall returns a presigned download URL on the transcript
                # object once the artifact is ready.
                dl = (
                    meta.get("download_url")
                    or (meta.get("data") or {}).get("download_url")
                )
                payload: Any
                if dl:
                    payload = recall_service.download_transcript_payload(dl)
                else:
                    payload = meta
                inv.recall_transcript_json = payload
                inv.recall_transcript_path = _persist_transcript(inv, payload, fmt="final")
                # Mirror into interview_transcripts so AI Analysis can find it.
                _mirror_into_interview_transcripts(db, inv, payload)
                inv.recall_status = "done"
                inv.recall_status_message = "Transcript ready."
            except recall_service.RecallAPIError as exc:
                inv.recall_status = "failed"
                inv.recall_status_message = f"transcript fetch failed: {exc}"

    elif event_type in ("transcript.data", "transcript.partial_data"):
        # Real-time: append the chunk and broadcast over SSE.
        chunk = data.get("data") or data
        # ``recall_transcript_json`` accumulates the live stream as a list.
        existing = inv.recall_transcript_json
        if not isinstance(existing, list):
            existing = []
        existing.append(chunk)
        inv.recall_transcript_json = existing
        inv.recall_status = inv.recall_status or "recording"
        _broadcast_chunk(inv.id, chunk)
        # Don't persist every partial to disk — only on transcript.done.

    else:
        logger.info("[Recall] webhook event %s — no handler", event_type)

    db.commit()
    return {"ok": True, "event": event_type, "interview_id": str(inv.id)}
