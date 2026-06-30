"""
PATHS Backend — In-app assistant (support chatbot) memory.

One row per chat message. Memory is scoped per (user, context_key, entity_id)
so the floating assistant keeps a SEPARATE conversation thread for each place
in the app — the dashboard thread, the jobs thread, each individual job, each
candidate profile, etc. This is the persistent (long-term) half of the
assistant's hybrid memory; the recent window of these rows is replayed into the
prompt as short-term working memory.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssistantMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index(
            "ix_assistant_thread",
            "user_id", "context_key", "entity_id", "created_at",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Memory is per-user: each recruiter has their own assistant history.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The page/section the chat belongs to (e.g. "dashboard", "jobs",
    # "candidate"). entity_id pins it to a specific record (a job id, a
    # candidate id, …) or is "" for list/section pages.
    context_key: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default="",
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
