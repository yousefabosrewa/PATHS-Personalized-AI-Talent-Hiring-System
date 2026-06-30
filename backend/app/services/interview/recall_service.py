"""
PATHS Backend — Recall.ai notetaker bot integration.

Wraps the four Recall.ai endpoints the interview flow needs:

  POST  /api/v1/bot                                          — dispatch a bot to a meeting URL
  POST  /api/v1/bot/{bot_id}/leave_call                      — stop the bot mid-call
  GET   /api/v1/bot/{bot_id}                                 — poll bot status
  POST  /api/v1/recording/{recording_id}/create_transcript/  — request async transcript
  GET   /api/v1/transcript/{transcript_id}/                  — fetch finished transcript

Plus:

  * ``verify_webhook_signature`` for inbound webhook auth (Svix-style).
  * ``RecallNotConfigured`` exception so endpoints can 503 cleanly when
    ``RECALL_API_KEY`` is blank (the integration is intentionally dormant
    until the operator pastes a key into ``.env``).

The client is deliberately tiny — every call goes through ``_request``
which centralises auth, region, timeout, and error handling so the rest
of the codebase never has to care about HTTP details.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ── Constants + exceptions ───────────────────────────────────────────────


class RecallNotConfigured(RuntimeError):
    """Raised when an operation needs Recall but ``RECALL_API_KEY`` is blank."""


class RecallAPIError(RuntimeError):
    """Wraps a non-2xx response from Recall so callers can log a tidy message."""

    def __init__(self, status_code: int, message: str, *, body: Any | None = None) -> None:
        super().__init__(f"recall.ai {status_code}: {message}")
        self.status_code = status_code
        self.body = body


_DEFAULT_TIMEOUT = 30.0


# Recording mode literals used across the backend + frontend.
RECORDING_MODE_POST = "post_meeting"
RECORDING_MODE_REAL_TIME = "real_time"
VALID_RECORDING_MODES = (RECORDING_MODE_POST, RECORDING_MODE_REAL_TIME)


# ── Helpers ──────────────────────────────────────────────────────────────


def is_configured() -> bool:
    """True iff the operator has set RECALL_API_KEY in .env."""
    return bool(get_settings().recall_api_key.strip())


def _base_url() -> str:
    s = get_settings()
    region = (s.recall_region or "eu-central-1").strip()
    return f"https://{region}.recall.ai/api/v1"


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.recall_api_key.strip():
        raise RecallNotConfigured(
            "RECALL_API_KEY is empty — set it in backend/.env to enable the "
            "Recall.ai notetaker."
        )
    # Recall expects ``Authorization: Token <api_key>`` per their docs. The
    # newer dashboard sometimes prints just the key — we tolerate both by
    # only adding the ``Token `` prefix when missing.
    raw = s.recall_api_key.strip()
    auth = raw if raw.lower().startswith(("token ", "bearer ")) else f"Token {raw}"
    return {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.request(method, url, headers=_headers(), json=json_body)
    except httpx.HTTPError as exc:
        logger.warning("[Recall] network error %s %s: %s", method, url, exc)
        raise RecallAPIError(0, f"network error: {exc}") from exc
    if not r.is_success:
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = r.text
        logger.warning("[Recall] %s %s -> %s %s", method, url, r.status_code, body)
        raise RecallAPIError(r.status_code, r.reason_phrase or "http error", body=body)
    if r.status_code == 204 or not r.content:
        return {}
    try:
        return r.json()
    except Exception as exc:  # noqa: BLE001
        raise RecallAPIError(r.status_code, f"non-JSON response: {exc}") from exc


# ── Bot lifecycle ────────────────────────────────────────────────────────


def create_bot(
    *,
    meeting_url: str,
    bot_name: str | None = None,
    join_at: datetime | None = None,
    real_time_transcript: bool = False,
    real_time_endpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch a bot to a meeting URL.

    ``real_time_transcript`` toggles Recall's ``transcript.data`` webhook
    delivery — the backend uses those events to push live captions into
    the SSE stream the dashboard listens on.

    ``real_time_endpoint`` is the absolute URL Recall should POST
    ``transcript.data`` events to.  When omitted Recall falls back to
    the workspace-level webhook config so we still get them — but
    callers should pass it explicitly when the public webhook URL is
    known so the routing stays scoped.
    """
    settings = get_settings()
    body: dict[str, Any] = {
        "meeting_url": meeting_url,
        "bot_name": (bot_name or settings.recall_bot_name or "PATHS Notetaker"),
        # A polite on-join chat message — Recall recommends this for
        # consent transparency.
        "chat": {
            "on_bot_join": {
                "send_to": "everyone",
                "message": (
                    "This interview is being recorded and transcribed by "
                    "the PATHS notetaker."
                ),
                "pin": True,
            },
        },
    }
    if join_at is not None:
        body["join_at"] = join_at.isoformat()
    if metadata:
        body["metadata"] = metadata

    # Real-time mode: enable transcript.data event stream. The
    # ``recallai_streaming`` provider keeps the cost low while still
    # giving us interim + final words during the call.
    if real_time_transcript:
        provider_block: dict[str, Any] = {
            "recallai_streaming": {"language_code": "auto"},
        }
        body["recording_config"] = {
            "transcript": {"provider": provider_block},
            "realtime_endpoints": (
                [
                    {
                        "type": "webhook",
                        "url": real_time_endpoint,
                        "events": ["transcript.data", "transcript.partial_data"],
                    }
                ]
                if real_time_endpoint
                else []
            ),
        }
    return _request("POST", "/bot", json_body=body)


def stop_bot(bot_id: str) -> dict[str, Any]:
    """Tell the bot to leave the call now."""
    return _request("POST", f"/bot/{bot_id}/leave_call")


def get_bot(bot_id: str) -> dict[str, Any]:
    return _request("GET", f"/bot/{bot_id}")


def extract_video_url(bot: Any) -> str | None:
    """Best-effort pull of a playable mixed-video URL from a Recall bot or
    recording object. Tolerates schema drift across Recall API versions
    (``recordings[].media_shortcuts.video_mixed.data.download_url`` and a
    handful of flatter fallbacks)."""
    if not isinstance(bot, dict):
        return None
    candidates: list[Any] = []
    recordings = bot.get("recordings")
    if isinstance(recordings, list):
        candidates.extend(recordings)
    candidates.append(bot)  # some responses nest media on the bot directly
    for rec in candidates:
        if not isinstance(rec, dict):
            continue
        shortcuts = rec.get("media_shortcuts") or rec.get("media") or {}
        if isinstance(shortcuts, dict):
            for key in ("video_mixed", "video", "video_separate"):
                node = shortcuts.get(key)
                if isinstance(node, dict):
                    data = node.get("data") if isinstance(node.get("data"), dict) else {}
                    url = (
                        data.get("download_url")
                        or node.get("download_url")
                        or node.get("url")
                    )
                    if isinstance(url, str) and url.startswith("http"):
                        return url
        for key in ("video_url", "mp4_url", "download_url"):
            url = rec.get(key)
            if isinstance(url, str) and url.startswith("http"):
                return url
    return None


def get_recording_video_url(bot_id: str) -> str | None:
    """Fetch the bot and extract a playable (signed, time-limited) video URL.
    Returns ``None`` when Recall is unreachable or no recording exists — the
    report degrades gracefully rather than erroring."""
    if not bot_id:
        return None
    try:
        bot = get_bot(bot_id)
    except (RecallAPIError, RecallNotConfigured):
        return None
    return extract_video_url(bot)


# ── Transcript ───────────────────────────────────────────────────────────


def create_async_transcript(
    recording_id: str, *, language_code: str = "auto",
) -> dict[str, Any]:
    """Kick off async post-meeting transcription against a finished
    recording. Returns the transcript object (with ``id``)."""
    body = {
        "provider": {"recallai_async": {"language_code": language_code}},
        "diarization": {"use_separate_streams_when_available": True},
    }
    return _request(
        "POST",
        f"/recording/{recording_id}/create_transcript/",
        json_body=body,
    )


def get_transcript(transcript_id: str) -> dict[str, Any]:
    """Fetch the finished transcript JSON (Recall returns a download URL
    when the artifact is ready)."""
    return _request("GET", f"/transcript/{transcript_id}/")


def download_transcript_payload(download_url: str, *, timeout: float = 60.0) -> Any:
    """Recall returns the transcript text as a presigned URL — fetch it."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(download_url)
    except httpx.HTTPError as exc:
        raise RecallAPIError(0, f"download network error: {exc}") from exc
    if not r.is_success:
        raise RecallAPIError(r.status_code, r.reason_phrase or "transcript download failed")
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return r.text


# ── Webhook signature verification ───────────────────────────────────────


def verify_webhook_signature(
    *,
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    secret: str | None = None,
) -> bool:
    """Verify an inbound Recall webhook using the Svix signing scheme.

    Recall (like many providers) signs every webhook with a base64 HMAC
    over the string ``{id}.{timestamp}.{body}`` keyed off the workspace
    secret. The header ``svix-signature`` contains one or more space-
    separated ``v1,base64sig`` values — any one matching is accepted.

    A blank secret disables verification and returns True (development
    fallback). Operators should always set ``RECALL_WEBHOOK_SECRET`` in
    production.
    """
    secret = (secret or get_settings().recall_webhook_secret or "").strip()
    if not secret:
        logger.warning(
            "[Recall] webhook signature check skipped — RECALL_WEBHOOK_SECRET is empty"
        )
        return True
    if not (svix_id and svix_timestamp and svix_signature):
        return False
    # Svix secrets are prefixed with ``whsec_`` and stored base64-encoded.
    key_b64 = secret.removeprefix("whsec_")
    try:
        key = base64.b64decode(key_b64)
    except Exception:  # noqa: BLE001
        # Tolerate raw-secret form for self-hosted Recall webhooks.
        key = secret.encode("utf-8")
    signed_payload = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + payload
    expected = hmac.new(key, signed_payload, hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode("ascii")
    for sig in svix_signature.split():
        parts = sig.split(",", 1)
        if len(parts) != 2:
            continue
        candidate = parts[1]
        if hmac.compare_digest(candidate, expected_b64):
            return True
    return False


# ── Lightweight JSON helpers used by callers ─────────────────────────────


def normalize_status(raw: Any) -> str:
    """Turn whatever Recall returns into the canonical lowercase status
    code we persist on ``interviews.recall_status``."""
    if not raw:
        return "pending"
    if isinstance(raw, dict):
        raw = raw.get("code") or raw.get("status") or raw.get("name") or ""
    return str(raw).strip().lower().replace("-", "_") or "pending"


def transcript_to_text(payload: Any) -> str:
    """Best-effort flattener so the UI can show a plain-text fallback.

    Recall's JSON transcript schema looks like ``[{ "speaker": "...",
    "words": [{ "text": "..." }, ...] }, ...]``. We tolerate other shapes
    (e.g. ``{"segments": [...]}``) so future schema tweaks don't crash
    the dashboard.
    """
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("segments", "transcript", "data", "utterances"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
        else:
            return json.dumps(payload, ensure_ascii=False)
    if not isinstance(payload, list):
        return str(payload)

    lines: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        speaker = item.get("speaker") or item.get("participant", {}).get("name") or ""
        words = item.get("words") or []
        if isinstance(words, list) and words:
            text = " ".join(
                str(w.get("text") or w.get("word") or "").strip()
                for w in words
                if isinstance(w, dict)
            ).strip()
        else:
            text = (item.get("text") or item.get("transcript") or "").strip()
        if not text:
            continue
        lines.append(f"{speaker.strip() + ': ' if speaker else ''}{text}")
    return "\n".join(lines)
