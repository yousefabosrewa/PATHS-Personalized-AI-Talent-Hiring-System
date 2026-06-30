"""ORM model for the agent_runs table — generic async agent execution tracker."""

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models.base import Base


class AgentRun(Base):
    """Tracks every long-running LangGraph agent invocation.

    All six agents (cv_ingestion, screening, interview_eval, sourcing,
    outreach, decision_support) write their progress here so the frontend
    can poll GET /api/v1/agent-runs/{id} and show a progress indicator.
    """

    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(String, nullable=False, index=True)

    # What kind of run this is
    run_type = Column(String(64), nullable=False)
    # queued → running → completed | failed
    status = Column(String(32), nullable=False, default="queued")
    # Which LangGraph node is currently executing
    current_node = Column(String(128), nullable=True)

    # Who triggered this run
    triggered_by = Column(String, nullable=True)

    # The entity this run is about (job, candidate, interview …)
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(String, nullable=True)

    # Serialised input/output references (avoids duplicating large blobs)
    input_ref = Column(JSONB, nullable=True)
    result_ref = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_runs_org_type", "organization_id", "run_type"),
        Index("ix_agent_runs_entity", "entity_type", "entity_id"),
        Index("ix_agent_runs_status", "status"),
    )
