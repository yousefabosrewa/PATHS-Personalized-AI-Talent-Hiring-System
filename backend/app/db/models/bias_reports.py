"""
PATHS Backend — BiasReport ORM model.

One row per (screening_run × protected_attribute × group_label).
Written by the bias_guardrail_node after each screening run.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.models.base import Base


class BiasReport(Base):
    """Disparate-impact metrics for one group within one screening run."""

    __tablename__ = "bias_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    screening_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("screening_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Protected attribute name — "gender", "age", "race_ethnicity", …
    attribute_name = Column(String(80), nullable=False)
    # Specific group label — "female", "25-34", "Black or African American", …
    group_label = Column(String(120), nullable=False)

    # Raw counts
    selection_count = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)

    # Derived metrics
    selection_rate = Column(Float, nullable=False, default=0.0)
    # NULL for the reference (highest-rate) group; computed for all others
    disparate_impact_ratio = Column(Float, nullable=True)

    # Threshold from the job's fairness rubric at time of run
    threshold = Column(Float, nullable=False, default=0.8)
    # False = this group triggered a fairness flag
    passed = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    screening_run = relationship("ScreeningRun", back_populates="bias_reports")

    def __repr__(self) -> str:
        return (
            f"<BiasReport run={self.screening_run_id} "
            f"attr={self.attribute_name}:{self.group_label} "
            f"rate={self.selection_rate:.2f} passed={self.passed}>"
        )
