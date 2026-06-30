"""
OpenRouter client for structured JSON (Decision Support, development plans, emails).

Never logs API keys. Retries once on invalid JSON with a repair hint.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.scoring.llama_scoring_agent import _balanced_object

logger = logging.getLogger(__name__)
settings = get_settings()

# A model that returns HTTP 429 gets one quick retry (honouring Retry-After);
# if it is still limited the caller falls through to the next free model.
_MAX_429_RETRIES = 1


class OpenRouterClientError(RuntimeError):
    """OpenRouter request failed or returned unusable data."""


def _redact(s: str) -> str:
    if settings.openrouter_api_key:
        s = s.replace(settings.openrouter_api_key, "***")
    return s[:800]


def _parse_json_object(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        out = json.loads(t)
    except json.JSONDecodeError:
        snip = _balanced_object(t)
        if not snip:
            raise OpenRouterClientError("response did not contain a JSON object")
        out = json.loads(snip)
    if not isinstance(out, dict):
        raise OpenRouterClientError("JSON root must be an object")
    return out


def _chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list[dict[str, str]] | None = None,
    retry_on_429: bool = True,
) -> str:
    if not settings.openrouter_api_key:
        raise OpenRouterClientError("OPENROUTER_API_KEY is not configured")
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_referer or "https://paths.local",
        "X-Title": settings.openrouter_app_title or "PATHS",
    }
    # A multi-turn `messages` list (system + history + latest user turn) takes
    # precedence; otherwise fall back to the single system+user shape.
    chat_messages = messages or [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    body: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    to = max(5.0, float(settings.dss_openrouter_timeout_seconds or 120.0))
    r: httpx.Response | None = None
    for attempt in range(_MAX_429_RETRIES + 1):
        with httpx.Client(timeout=to) as client:
            r = client.post(url, headers=headers, json=body)
        # `retry_on_429=False` (the interactive assistant) fails fast so the
        # caller can fall through to the next model instead of sleeping.
        if r.status_code != 429 or attempt == _MAX_429_RETRIES or not retry_on_429:
            break
        try:
            retry_after = float(r.headers.get("Retry-After") or 0)
        except ValueError:
            retry_after = 0.0
        wait = min(max(retry_after, 2.0), 8.0)
        logger.warning(
            "OpenRouter 429 rate-limited — retry %s/%s in %.0fs",
            attempt + 1, _MAX_429_RETRIES, wait,
        )
        time.sleep(wait)
    if r is None or r.status_code >= 400:
        code = r.status_code if r is not None else "no-response"
        text = r.text if r is not None else ""
        raise OpenRouterClientError(_redact(f"openrouter {code}: {text}"))
    data = r.json()
    ch = (data.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    if not isinstance(content, str):
        raise OpenRouterClientError("empty or non-text content in response")
    return content.strip()


def _candidate_models(requested: str | None) -> list[str]:
    """Primary model first, then the configured free-model fallbacks.

    Free OpenRouter models are rate-limited per shared upstream provider, so
    when one returns 429 we fall through to other free models (different
    providers) — keeping the whole pipeline on the free tier.
    """
    chain: list[str] = []
    primary = (requested or settings.openrouter_dss_model or "").strip()
    if primary:
        chain.append(primary)
    for m in (settings.openrouter_free_fallback_models or "").split(","):
        m = m.strip()
        if m and m not in chain:
            chain.append(m)
    return chain or [settings.openrouter_dss_model]


def _is_model_unavailable(err: str) -> bool:
    """True for errors where falling through to a different model is worthwhile."""
    low = (err or "").lower()
    return any(
        s in low
        for s in (
            "429", "rate-limit", "rate limit", "rate_limit", "temporarily",
            "overloaded", " 502", " 503", " 529", "is not a valid model",
        )
    )


def generate_chat_response(
    system_prompt: str,
    history: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 700,
) -> str:
    """Return a plain-text assistant reply for a multi-turn conversation.

    ``history`` is a list of ``{"role": "user"|"assistant", "content": ...}``
    turns (the latest user message last). Uses the same free-model fallback
    chain as ``generate_json_response`` so rate limits fall through cleanly.
    """
    messages = [{"role": "system", "content": system_prompt}, *history]
    last_err: str | None = None
    for m in _candidate_models(model):
        try:
            return _chat(
                system_prompt,
                "",
                model=m,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                retry_on_429=False,  # fail fast → fall through to next model
            )
        except OpenRouterClientError as exc:
            last_err = str(exc)
            if _is_model_unavailable(last_err):
                logger.warning(
                    "OpenRouter model '%s' unavailable — trying next free model", m,
                )
                continue
            raise
    raise OpenRouterClientError(last_err or "all candidate models failed")


def generate_json_response(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    """Return a dict parsed from model JSON.

    Retries once per model on invalid JSON, and falls through a chain of free
    models when a model is rate-limited (429) or otherwise unavailable.
    """
    models = _candidate_models(model)
    last_err: str | None = None
    for m in models:
        for attempt in range(2):
            up = user_prompt
            if attempt == 1:
                up = (
                    user_prompt
                    + "\n\nYour previous output was not valid JSON. "
                    "Reply with ONLY a single valid JSON object, no markdown."
                )
            try:
                raw = _chat(system_prompt, up, model=m, temperature=temperature, max_tokens=max_tokens)
                return _parse_json_object(raw)
            except OpenRouterClientError as exc:
                last_err = str(exc)
                if _is_model_unavailable(last_err):
                    logger.warning(
                        "OpenRouter model '%s' unavailable — trying next free model", m,
                    )
                    break  # stop retrying this model; fall through to the next
                raise  # auth / config errors — surface immediately
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                last_err = str(exc)
                logger.warning(
                    "OpenRouter JSON parse failed (model=%s, attempt=%s): %s",
                    m, attempt, last_err,
                )
                if attempt == 1:
                    break  # invalid JSON twice from this model — try the next
    raise OpenRouterClientError(last_err or "all candidate models failed")
