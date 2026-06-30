"""
PATHS Backend — Organization model.

Adds the platform-admin approval workflow:
  - Organization.status               (pending_approval | active | rejected | suspended)
  - Organization.approved_by_admin_id / approved_at
  - Organization.rejected_by_admin_id / rejected_at / rejection_reason
  - Organization.suspended_at / suspended_reason

The legacy `is_active` boolean is kept for backwards compatibility — services
that still read it will continue to work. New code should consult `status`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationStatus(str, PyEnum):
    """Lifecycle status of an Organization (string-valued for DB portability)."""

    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Dedicated columns so the org profile no longer crams everything into the
    # single `industry` string at signup.
    company_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Approval workflow (added in platform-admin migration) ────────────────
    # `status` is the source of truth. is_active is derived (kept for legacy
    # readers) but write paths set both fields for safety.
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OrganizationStatus.ACTIVE.value, index=True,
    )
    approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── LinkedIn account for sourcing (fix6.md follow-up) ────────────────────
    # Set when a recruiter connects their LinkedIn from Organization settings.
    # Cookies are encrypted at rest using the project secret_key.
    linkedin_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_li_at_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_jsessionid_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    linkedin_connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    # Relationships
    members = relationship("OrganizationMember", back_populates="organization", lazy="selectin")
    jobs = relationship("Job", back_populates="organization", lazy="selectin")
    access_requests = relationship(
        "OrganizationAccessRequest",
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrganizationAccessRequestStatus(str, PyEnum):
    """Lifecycle of a company access request created at signup time."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrganizationAccessRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A pending application for company access. Created when someone signs the
    company representative up via /api/v1/auth/register/organization. A
    platform admin then approves or rejects it via /api/v1/admin/org-requests.

    On approval: Organization.status flips to 'active', the requester's
    OrganizationMember row becomes active, and the user can log in to the
    company workspace.
    """

    __tablename__ = "organization_access_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True,
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OrganizationAccessRequestStatus.PENDING.value, index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Self-described context the requester provided in the signup form.
    contact_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="access_requests", lazy="selectin")
