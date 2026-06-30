"""
PATHS Backend — Bias Guardrail (Phase 4).

Enforces Blueprint Law #2 at every scoring entry point.

Public API
----------
check_before_scoring(db, candidate_id, job_id, org_id, actor_id)
    → AnonymizedView   raises GuardrailBlockedError if the check fails

log_bias_audit(db, event_type, *, candidate_id, job_id, org_id, actor_id, detail)
    → None   (fire-and-forget append to bias_audit_log)

raise_bias_flag(db, org_id, scope, scope_id, rule, severity, detail)
    → BiasFlag
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.bias_fairness import BiasAuditLog, BiasFlag
from app.services.bias_fairness.anonymizer import get_or_create_view

logger = logging.getLogger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────────


class GuardrailBlockedError(RuntimeError):
    """Raised when the guardrail blocks a pipeline transition."""

    def __init__(self, reason: str, flag_rule: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.flag_rule = flag_rule


# ── Main check ────────────────────────────────────────────────────────────────


def check_before_scoring(
    db: Session,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None,
    *,
    org_id: str | None = None,
    actor_id: str | None = None,
) -> Any:  # returns AnonymizedView
    """Ensure a valid AnonymizedView exists before any scoring agent runs.

    Steps:
      1. Call get_or_create_view — creates the view if absent or stale.
      2. Log 'anonymized_view_used' to bias_audit_log.
      3. Return the view so the caller can pass view_json to the agent.

    Raises GuardrailBlockedError if the view cannot be built (e.g. missing profile).
    """
    try:
        view = get_or_create_view(db, candidate_id)
    except ValueError as exc:
        rule = "missing_candidate_profile"
        log_bias_audit(
            db,
            "pii_access_blocked",
            candidate_id=str(candidate_id),
            job_id=str(job_id) if job_id else None,
            org_id=org_id,
            actor_id=actor_id,
            detail={"reason": str(exc), "rule": rule},
        )
        raise GuardrailBlockedError(str(exc), flag_rule=rule) from exc

    # Log successful anonymized view consumption.
    log_bias_audit(
        db,
        "anonymized_view_used",
        candidate_id=str(candidate_id),
        job_id=str(job_id) if job_id else None,
        org_id=org_id,
        actor_id=actor_id,
        detail={
            "view_id": str(view.id),
            "view_version": view.view_version,
            "stripped_fields": view.stripped_fields or [],
        },
    )
    return view


# ── Bias audit log writer ─────────────────────────────────────────────────────


def log_bias_audit(
    db: Session,
    event_type: str,
    *,
    candidate_id: str | None = None,
    job_id: str | None = None,
    org_id: str | None = None,
    actor_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append a row to bias_audit_log. Never raises — errors are suppressed
    so a logging failure never blocks the pipeline."""
    try:
        entry = BiasAuditLog(
            event_type=event_type,
            candidate_id=candidate_id,
            job_id=job_id,
            org_id=org_id,
            actor_id=actor_id,
            detail_json=detail or {},
        )
        db.add(entry)
        db.flush()   # write to DB within the caller's transaction
        logger.debug("[BiasAudit] %s candidate=%s job=%s", event_type, candidate_id, job_id)
    except Exception:
        logger.exception("[BiasAudit] failed to write audit event %s", event_type)


# ── Bias flag writer ──────────────────────────────────────────────────────────


def raise_bias_flag(
    db: Session,
    org_id: uuid.UUID,
    scope: str,
    scope_id: str,
    rule: str,
    severity: str = "medium",
    detail: dict[str, Any] | None = None,
) -> BiasFlag:
    """Create a BiasFlag row and log to bias_audit_log."""
    flag = BiasFlag(
        id=uuid.uuid4(),
        org_id=org_id,
        scope=scope,
        scope_id=scope_id,
        rule=rule,
        severity=severity,
        status="open",
        detail=detail or {},
    )
    db.add(flag)
    db.flush()

    log_bias_audit(
        db,
        "bias_flag_raised",
        org_id=str(org_id),
        detail={"scope": scope, "scope_id": scope_id, "rule": rule, "severity": severity},
    )
    logger.warning(
        "[BiasGuardrail] flag raised scope=%s id=%s rule=%s severity=%s",
        scope, scope_id, rule, severity,
    )
    return flag
