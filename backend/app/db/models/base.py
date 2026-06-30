"""
PATHS Backend — SQLAlchemy declarative base and common mixins.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all PATHS models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        # `default` populates updated_at on INSERT (client-side, always sent),
        # `onupdate` refreshes it on UPDATE. Without `default`, INSERTs sent
        # NULL — which fails on any table whose updated_at column is NOT NULL.
        default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
