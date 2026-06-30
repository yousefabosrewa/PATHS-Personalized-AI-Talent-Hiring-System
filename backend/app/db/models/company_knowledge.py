"""
PATHS Backend — Company Knowledge File model (fix2_1.md Feature 1).

Stores company documents an organisation uploads so agents understand the
company better (culture, policies, role levels, tech stack, etc.). Files are
org-scoped; legal/compliance files are flagged as read-only reference context.

Indexing: the extracted text is chunked and embedded into the
``company_knowledge`` Qdrant collection with org-scoped payload so only
agents operating in the same organisation context retrieve it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# Allowed categories (kept in sync with the frontend selector).
COMPANY_FILE_CATEGORIES: tuple[str, ...] = (
    "company_overview",
    "culture_and_values",
    "hiring_policy",
    "role_levels_and_career_paths",
    "benefits_and_compensation",
    "technical_stack",
    "team_structure",
    "interview_guidelines",
    "onboarding_documents",
    "legal_compliance_reference",
    "other",
)

# The single category that marks a file as protected legal/compliance context.
LEGAL_CATEGORY = "legal_compliance_reference"


class CompanyKnowledgeFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "company_knowledge_files"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="other",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # uploaded | processing | indexed | failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded",
    )
    is_legal_or_compliance_context: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
