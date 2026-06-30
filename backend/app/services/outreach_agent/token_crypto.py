"""
PATHS Backend — Token encryption + scheduling token helpers.

Uses Fernet (AES-128-CBC + HMAC) seeded from `settings.secret_key`. Tokens
that go to candidates are random URL-safe strings; only their SHA-256 hash
is persisted in the DB.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_settings = get_settings()


def _derive_fernet_key(passphrase: str) -> bytes:
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET: Final[Fernet] = Fernet(_derive_fernet_key(_settings.secret_key))


def encrypt_secret(plaintext: str | None) -> str | None:
    if plaintext is None or plaintext == "":
        return None
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _FERNET.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def new_scheduling_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Persist only the hash."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    if a is None or b is None:
        return False
    return secrets.compare_digest(a, b)
