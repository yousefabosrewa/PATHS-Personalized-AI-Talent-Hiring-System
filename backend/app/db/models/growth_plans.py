"""ORM model for the growth_plans table — AI-generated candidate development plans."""

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.db.models.base import Base


class GrowthPlan(Base):
    """AI-generated personalised development plan for a candidate.

    Created by the Decision Support agent after a hire decision.
    Contains 30/60/90-day milestones, skill gaps, and learning resources.
    """

    __tablename__ = "growth_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(String, nullable=False, index=True)
    candidate_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=True)

    # Link back to the decision that triggered this plan
    decision_id = Column(String, nullable=True)
    agent_run_id = Column(UUID(as_uuid=True), nullable=True)
    generated_by_run_id = Column(UUID(as_uuid=True), nullable=True)

    # Core content (JSONB for schema flexibility)
    # [{skill, gap_level: low|medium|high, priority: int, resources: [...]}]
    skill_gaps = Column(JSONB, nullable=True)

    # [{title, url, type: course|book|video|article, estimated_hours}]
    learning_resources = Column(JSONB, nullable=True)

    # [{label: "30-day", goals: ["..."], success_criteria: "..."}]
    milestones = Column(JSONB, nullable=True)

    overall_completion = Column(Float, nullable=True, default=0.0)

    # draft | active | completed
    status = Column(String(32), nullable=False, default="draft")

    # Message shown to the candidate in their portal
    candidate_facing_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_growth_plans_candidate", "candidate_id"),
        Index("ix_growth_plans_org", "organization_id"),
    )
