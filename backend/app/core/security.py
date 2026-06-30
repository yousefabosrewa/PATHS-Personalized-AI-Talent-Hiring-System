"""
PATHS Backend — Security utilities.

Provides password hashing / verification and JWT token management.

Password algorithm: argon2id (PATHS-170).
Strategy: new passwords are hashed with argon2id. Legacy bcrypt hashes are
transparently verified on login and rehashed to argon2id on success (progressive
upgrade — no forced migration batch needed).
"""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# argon2id is the primary scheme; bcrypt is kept as deprecated fallback for
# existing hashes so they can be verified and progressively rehashed.
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__type="ID",
    argon2__time_cost=2,
    argon2__memory_cost=65536,  # 64 MiB
    argon2__parallelism=2,
)


# ── Password helpers ──────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plain-text password with argon2id."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against any stored hash (argon2id or legacy bcrypt)."""
    return pwd_context.verify(plain, hashed)


def needs_rehash(hashed: str) -> bool:
    """Return True if the stored hash uses an algorithm weaker than the current default.

    Call this after verify_password() succeeds. If True, rehash and persist the
    updated hash so the account progressively migrates to argon2id.
    """
    return pwd_context.needs_update(hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    ``data`` should contain at least ``{"sub": "<user-email>"}``.
    Additional claims (account_type, org_id, role_code) are embedded as-is.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT token.  Returns claims dict or None."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.InvalidTokenError:
        return None
