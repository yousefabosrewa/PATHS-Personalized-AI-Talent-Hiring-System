"""PATHS Backend — FairnessRubric model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class FairnessRubric(Base):
    __tablename__ = "fairness_rubric"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False,
    )
    # e.g. {"gender": true, "age_band": true, "location": false}
    protected_attrs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    disparate_impact_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    job = relationship("Job", back_populates="fairness_rubric", lazy="selectin")
