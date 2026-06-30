"""
PATHS Backend — AnalyticsEvent ORM model.

Append-only event stream.  Every significant action in the system
(job created, screening run completed, candidate moved, bias flagged, …)
appends one row here.  The analytics API endpoints aggregate over it.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.models.base import Base


class AnalyticsEvent(Base):
    """Single immutable event in the platform event stream."""

    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Coarse category — "job" | "candidate" | "application" |
    #   "screening_run" | "outreach" | "interview" | "decision"
    entity_type = Column(String(60), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Fine-grained action — "job_created", "screening_completed",
    #   "candidate_moved", "bias_flag", "offer_sent", …
    event_type = Column(String(80), nullable=False, index=True)

    # User who triggered the event; NULL for autonomous agent actions
    actor_id = Column(UUID(as_uuid=True), nullable=True)

    # Arbitrary JSON payload (stage name, score, attribute name, …)
    payload = Column(JSONB, nullable=False, default=dict)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AnalyticsEvent org={self.org_id} "
            f"type={self.entity_type}/{self.event_type} "
            f"entity={self.entity_id}>"
        )
