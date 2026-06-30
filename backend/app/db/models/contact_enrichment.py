from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EnrichedContact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enriched_contacts"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
    )
    contact_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="email | phone | linkedin | github | portfolio",
    )
    original_value: Mapped[str] = mapped_column(String(500), nullable=False)
    enriched_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="pending | approved | rejected",
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="manual | parsed_cv | email_validation | external_api",
    )
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EnrichedContact id={self.id!s:.8} type={self.contact_type} "
            f"candidate={self.candidate_id!s:.8} status={self.status}>"
        )
