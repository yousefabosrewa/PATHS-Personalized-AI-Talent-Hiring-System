"""Append-only audit trail rows for job import / scraper activity.

Uses the existing ``audit_events`` table (no schema changes).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.application import AuditEvent

logger = logging.getLogger(__name__)


def record_job_scraper_audit(
    session_factory,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    after: dict[str, Any] | None = None,
) -> None:
    """Best-effort write; failures are logged and swallowed."""
    session: Session = session_factory()
    try:
        session.add(
            AuditEvent(
                actor_type="system",
                actor_id="paths-job-scraper",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                after_jsonb=after,
            ),
        )
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("[JobScraperAudit] failed to write action=%s", action)
    finally:
        session.close()


__all__ = ["record_job_scraper_audit"]
