"""
PATHS Backend — In-process rate limiter.

Provides per-IP and per-account attempt counters with sliding-window TTL.
In production this should be replaced with a Redis-backed implementation
(e.g. fastapi-limiter) to work across multiple workers.

Usage:

    from app.core.rate_limit import check_rate_limit, record_failed_attempt, clear_attempts

    # In an endpoint, before processing:
    check_rate_limit(key="login:127.0.0.1", limit=5, window_seconds=600)

    # On a failed password attempt:
    locked = record_failed_attempt(key="account:user@example.com", threshold=10)
    if locked:
        raise HTTPException(423, detail="account_locked")

PATHS-171 (Phase 8 — Launch Hardening)
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request

# Thread-safe store: key → deque of timestamps
_store: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()

# Account lockout store: account_key → (failed_count, locked_until)
_lockout: dict[str, tuple[int, float]] = {}
_lockout_lock = threading.Lock()

_LOCKOUT_DURATION_SECONDS = 1800  # 30 minutes


def _clean_window(dq: deque[float], window: float, now: float) -> None:
    """Remove timestamps older than the window from a deque (in-place)."""
    cutoff = now - window
    while dq and dq[0] < cutoff:
        dq.popleft()


def check_rate_limit(key: str, limit: int, window_seconds: float) -> None:
    """
    Raise HTTP 429 if more than *limit* requests have been made from this *key*
    within the last *window_seconds* seconds.

    *key* is typically ``"<action>:<ip>"`` e.g. ``"login:192.168.1.1"``.
    """
    now = time.monotonic()
    with _lock:
        dq = _store[key]
        _clean_window(dq, window_seconds, now)
        if len(dq) >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limit_exceeded",
                    "message": f"Too many requests. Try again in {int(window_seconds // 60)} minutes.",
                },
            )
        dq.append(now)


def record_failed_attempt(account_key: str, threshold: int = 10) -> bool:
    """
    Record a failed authentication attempt for *account_key*
    (typically ``"account:<email>"``).

    Returns True if the account is now locked (≥ threshold failures).
    The lockout is automatically lifted after _LOCKOUT_DURATION_SECONDS.
    """
    now = time.monotonic()
    with _lockout_lock:
        count, locked_until = _lockout.get(account_key, (0, 0.0))
        if locked_until > now:
            return True  # Already locked
        count += 1
        if count >= threshold:
            _lockout[account_key] = (count, now + _LOCKOUT_DURATION_SECONDS)
            return True
        _lockout[account_key] = (count, 0.0)
        return False


def is_account_locked(account_key: str) -> bool:
    """Return True if the account is currently under a lockout."""
    now = time.monotonic()
    with _lockout_lock:
        count, locked_until = _lockout.get(account_key, (0, 0.0))
        if locked_until > now:
            return True
        if locked_until > 0:
            # Lockout expired — reset
            _lockout[account_key] = (0, 0.0)
        return False


def clear_attempts(account_key: str) -> None:
    """Clear failed attempt counter (call on successful login)."""
    with _lockout_lock:
        _lockout.pop(account_key, None)


def get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
