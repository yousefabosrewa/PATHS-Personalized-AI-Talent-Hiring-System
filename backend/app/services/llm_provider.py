"""
PATHS Backend — Unified LLM provider facade.

The actual implementation lives in
``app.services.organization_matching.organization_llm_provider`` (OpenRouter
+ Ollama with automatic fallback). This module re-exports it under the
brief-mandated path ``app/services/llm_provider.py`` and provides a thin
synchronous JSON helper used by interview/outreach/scoring agents that
prefer simple call sites over async chat shapes.

Public surface:

  get_provider()                 -> LLMProvider     # async chat interface
  generate_text(prompt, ...)     -> str             # sync sugar over OpenRouter
  generate_json(prompt, ...)     -> dict            # sync sugar over OpenRouter
  stream_text(prompt, ...)       -> AsyncIterator   # passes through to provider

Switch providers via env:
  LLM_PROVIDER=openrouter|ollama        (default: openrouter)
  LOCAL_LLM_ENABLED=true|false          (forces local even when OpenRouter is set)
  LLM_ALLOW_FALLBACK_TO_OLLAMA=true     (OpenRouter -> Ollama on failure)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Iterable

from app.core.config import get_settings
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)
from app.services.organization_matching.organization_llm_provider import (
    LLMProvider,
    LLMProviderError,
    get_provider as _get_provider,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Provider selection helpers ──────────────────────────────────────────


def _local_enabled() -> bool:
    """``LOCAL_LLM_ENABLED`` overrides the default provider selection."""
    return bool(getattr(settings, "local_llm_enabled", False))


def get_provider() -> LLMProvider:
    """Return the singleton chat-style LLM provider."""
    return _get_provider()


# ── Sync sugar (used by interview agents that don't need streaming) ─────


def _messages_from_prompt(prompt: str | list[dict[str, str]]) -> list[dict[str, str]]:
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    return list(prompt)


def generate_text(
    prompt: str | list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    """Run the prompt synchronously via the configured provider."""
    provider = get_provider()
    msgs = _messages_from_prompt(prompt)
    try:
        return asyncio.run(
            provider.generate_text(
                msgs, temperature=temperature, max_tokens=max_tokens,
            ),
        )
    except LLMProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
    # Surface as the same provider error so callers have one type to catch.
        raise LLMProviderError(str(exc)) from exc


def generate_json(
    prompt: str | list[dict[str, str]],
    *,
    schema: dict[str, Any] | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """JSON-only output. Uses OpenRouter's deterministic JSON helper when
    available; falls back to the chat provider otherwise.

    ``schema`` is accepted for API compatibility with the brief but is not
    enforced (the project keeps schema validation in pydantic models on
    the caller side).
    """
    _ = schema
    if not _local_enabled() and settings.openrouter_api_key:
        if isinstance(prompt, str):
            sys_msg = (
                "You are a precise JSON generator. Reply with one valid JSON "
                "object only, no markdown fences."
            )
            user_msg = prompt
        else:
            sys_chunks = [m["content"] for m in prompt if m.get("role") == "system"]
            user_chunks = [m["content"] for m in prompt if m.get("role") != "system"]
            sys_msg = "\n\n".join(sys_chunks) or (
                "You are a precise JSON generator. Reply with one valid JSON "
                "object only, no markdown fences."
            )
            user_msg = "\n\n".join(user_chunks)
        try:
            return generate_json_response(
                sys_msg,
                user_msg,
                temperature=temperature,
                max_tokens=max_tokens or 1500,
            )
        except OpenRouterClientError as exc:
            logger.warning("[LLM] OpenRouter JSON path failed: %s", exc)

    # Chat-provider fallback — let the provider parse JSON.
    provider = get_provider()
    msgs = _messages_from_prompt(prompt)
    try:
        return asyncio.run(
            provider.generate_json(
                msgs, temperature=temperature, max_tokens=max_tokens,
            ),
        )
    except LLMProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMProviderError(str(exc)) from exc


async def stream_text(
    prompt: str | list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Stream text chunks. Caller is responsible for assembly."""
    provider = get_provider()
    msgs = _messages_from_prompt(prompt)
    async for chunk in provider.stream_text(
        msgs, temperature=temperature, max_tokens=max_tokens,
    ):
        yield chunk


__all__ = [
    "LLMProvider",
    "LLMProviderError",
    "generate_json",
    "generate_text",
    "get_provider",
    "stream_text",
]
