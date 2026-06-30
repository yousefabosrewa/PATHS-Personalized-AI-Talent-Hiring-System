"""
PATHS Backend — Candidate Job-Description Analysis history.

Persists every JD-vs-profile analysis a candidate runs (the pasted job
description + the structured result) so they build up a list they can revisit —
newest first, click to see what they wrote and the result they got.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JdAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "jd_analyses"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_description_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
