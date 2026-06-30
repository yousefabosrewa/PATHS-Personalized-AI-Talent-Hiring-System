"""
PATHS Backend — Admin & Owner ORM models.

feature_flags, feature_flag_overrides, platform_settings,
announcements, impersonation_sessions.

PATHS-140 (Phase 7 — Admin & Owner Portals)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    overrides: Mapped[list["FeatureFlagOverride"]] = relationship(
        "FeatureFlagOverride", back_populates="flag", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.code} enabled={self.enabled}>"


class FeatureFlagOverride(Base):
    __tablename__ = "feature_flag_overrides"
    __table_args__ = (
        UniqueConstraint("flag_id", "org_id", name="uq_ffo_flag_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feature_flags.id", ondelete="CASCADE")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    flag: Mapped["FeatureFlag"] = relationship("FeatureFlag", back_populates="overrides")


class PlatformSettings(Base):
    """Singleton — always id=1."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="PATHS Platform"
    )
    support_email: Mapped[str | None] = mapped_column(String(200))
    legal_company_name: Mapped[str | None] = mapped_column(String(300))
    default_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_templates: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_app_banner_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banner_color: Mapped[str] = mapped_column(String(20), nullable=False, default="blue")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Announcement id={self.id} banner={self.in_app_banner_enabled}>"


class ImpersonationSession(Base):
    __tablename__ = "impersonation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    impersonator_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return (
            f"<ImpersonationSession "
            f"by={self.impersonator_account_id} "
            f"target={self.target_account_id}>"
        )
