"""
PATHS Backend — Authentication endpoints.

Includes forgot/reset-password flow (PATHS-125).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.logging import get_logger
from app.core.rate_limit import (
    check_rate_limit,
    clear_attempts,
    get_client_ip,
    is_account_locked,
    record_failed_attempt,
)
from app.core.security import hash_password
from app.db.models.billing import PasswordResetToken
from app.db.models.user import User
from app.schemas.auth import (
    CandidateRegisterRequest,
    CandidateRegisterResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrganizationRegisterRequest,
    OrganizationRegisterResponse,
)
from app.services import auth_service

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Forgot / Reset password schemas ──────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str = "If that email is registered, a reset link has been sent."


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    detail: str = "Password reset successfully."


@router.post(
    "/register/candidate",
    response_model=CandidateRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_candidate(
    data: CandidateRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new candidate."""
    return auth_service.register_candidate(db, data)


@router.post(
    "/register/organization",
    response_model=OrganizationRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_organization(
    data: OrganizationRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new organization and its first administrative user."""
    return auth_service.register_organization(db, data)


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate and return a JWT access token.

    Rate-limited: 10 attempts per 10 minutes per IP.
    Account lockout: 10 consecutive failures locks the account for 30 minutes.
    """
    ip = get_client_ip(request)
    # Per-IP rate limit: 10 attempts / 10 minutes
    check_rate_limit(f"login:{ip}", limit=10, window_seconds=600)

    # Account-level lockout check
    account_key = f"account:{data.email.lower()}"
    if is_account_locked(account_key):
        raise HTTPException(
            status_code=423,
            detail={
                "code": "account_locked",
                "message": "Too many failed attempts. Try again in 30 minutes or reset your password.",
            },
        )

    try:
        result = auth_service.login(db, data)
        # Successful login — clear any lockout counters
        clear_attempts(account_key)
        return result
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            locked = record_failed_attempt(account_key, threshold=10)
            if locked:
                raise HTTPException(
                    status_code=423,
                    detail={
                        "code": "account_locked",
                        "message": "Account locked after too many failures. Reset your password.",
                    },
                )
        raise


@router.get("/me", response_model=MeResponse)
def get_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get the current authenticated user context, including profile and org memberships."""
    return auth_service.get_me_context(db, current_user)


# ── Forgot password ───────────────────────────────────────────────────────────


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit: 5 attempts per 10 minutes per IP
    ip = get_client_ip(request)
    check_rate_limit(f"forgot:{ip}", limit=5, window_seconds=600)
    """
    Initiate a password reset.

    Always returns 200 regardless of whether the email is registered
    to prevent email enumeration attacks.
    """
    user = db.query(User).filter(User.email == str(data.email)).first()
    if not user:
        # Return success to avoid leaking which emails exist.
        return ForgotPasswordResponse()

    # Generate a secure random token
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

    # Invalidate previous tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)})

    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(prt)
    db.commit()

    # In dev/test: log the reset link; in prod: send email via SMTP
    from app.core.config import get_settings
    s = get_settings()
    reset_url = f"{s.app_frontend_url}/reset-password/{raw_token}"
    logger.info(
        "Password reset requested for %s. Token URL: %s",
        user.email,
        reset_url,
    )
    # TODO: replace the log with a real email send in production

    return ForgotPasswordResponse()


# ── Reset password ────────────────────────────────────────────────────────────


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(data: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit: 5 attempts per 10 minutes per IP
    ip = get_client_ip(request)
    check_rate_limit(f"reset:{ip}", limit=5, window_seconds=600)
    """
    Complete a password reset using the token from the email link.

    The token is single-use and expires after 2 hours.
    """
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    prt = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )
    if not prt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Update password
    user.hashed_password = hash_password(data.new_password)
    prt.used_at = now
    db.commit()

    logger.info("Password reset completed for user %s", user.email)
    return ResetPasswordResponse()


# ── GDPR: data export + account deletion (PATHS-175) ─────────────────────────


@router.get("/me/export")
def export_my_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Export all personal data for the current user as a JSON archive.

    This endpoint satisfies GDPR Article 20 (data portability).
    Candidates receive the full profile archive; org members receive account data.
    """
    from app.db.models.candidate import Candidate
    from sqlalchemy import select as _select

    if current_user.account_type == "candidate":
        cand = db.execute(
            _select(Candidate).where(Candidate.email == current_user.email)
        ).scalar_one_or_none()

        if cand:
            from app.services.gdpr_service import export_candidate_data
            data = export_candidate_data(str(cand.id), db)
        else:
            data = {"profile": {"email": current_user.email, "full_name": current_user.full_name}}
    else:
        data = {
            "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
            "user_id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "account_type": current_user.account_type,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        }
    return data


@router.delete("/me", status_code=204)
def delete_my_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Soft-delete the current user's account.

    - Immediately deactivates the account (is_active=False).
    - Hard-delete runs via daily cron 30 days later (PATHS-175).
    - Org members lose access immediately.
    """
    from app.db.models.candidate import Candidate
    from sqlalchemy import select as _select

    # Deactivate user
    current_user.is_active = False

    # If this is a candidate, soft-delete the candidate row too
    if current_user.account_type == "candidate":
        cand = db.execute(
            _select(Candidate).where(Candidate.email == current_user.email)
        ).scalar_one_or_none()
        if cand:
            from app.services.gdpr_service import soft_delete_candidate
            soft_delete_candidate(str(cand.id), db)

    db.commit()
    logger.info("Account soft-deleted for user %s", current_user.email)
