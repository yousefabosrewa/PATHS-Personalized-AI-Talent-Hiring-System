"""
PATHS Backend — Organisation health score.

Produces a 0–100 score for an org based on activity, commercial status,
and feature engagement.

Weights (per plan spec):
  Activity    50% — jobs posted, CVs processed, logins last 30d
  Commercial  30% — paid plan, on-time invoices
  Engagement  20% — feature adoption breadth

PATHS-141 (Phase 7 — Admin & Owner Portals)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.application import OrganizationMember
from app.db.models.billing import Invoice, Subscription
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.sync import AuditLog
from app.db.models.billing import UsageCounter


def compute_org_health(org_id: str, db: Session) -> int:
    """
    Return a 0–100 health score for an organisation.

    Safe to call on any org — returns 0 if the org doesn't exist.
    Never raises.
    """
    try:
        return _compute(org_id, db)
    except Exception:
        return 0


def _compute(org_id: str, db: Session) -> int:
    from uuid import UUID

    try:
        oid = UUID(org_id)
    except ValueError:
        return 0

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # ── Activity (50 pts) ─────────────────────────────────────────────────
    activity_score = 0

    # Jobs posted
    jobs = (
        db.query(func.count(Job.id))
        .filter(Job.organization_id == oid, Job.created_at >= thirty_days_ago)
        .scalar()
        or 0
    )
    activity_score += min(20, jobs * 4)  # 5 jobs = 20 pts

    # CVs processed (proxy via Candidate records created)
    cvs = (
        db.query(func.count(Candidate.id))
        .filter(
            Candidate.organization_id == oid,
            Candidate.created_at >= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    activity_score += min(15, cvs)  # 15 CVs = 15 pts

    # Logins (proxy: audit log entries)
    try:
        logins = (
            db.query(func.count(AuditLog.id))
            .filter(
                AuditLog.organization_id == str(oid),
                AuditLog.created_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )
    except Exception:
        logins = 0
    activity_score += min(15, logins // 2)

    # ── Commercial (30 pts) ───────────────────────────────────────────────
    commercial_score = 0

    sub = (
        db.query(Subscription)
        .filter(Subscription.org_id == oid, Subscription.status == "active")
        .first()
    )
    if sub:
        commercial_score += 20  # has active paid plan
        # Check last invoice
        last_inv = (
            db.query(Invoice)
            .filter(Invoice.org_id == oid)
            .order_by(Invoice.created_at.desc())
            .first()
        )
        if last_inv and last_inv.status == "paid":
            commercial_score += 10

    # ── Engagement (20 pts) ───────────────────────────────────────────────
    engagement_score = 0

    # Feature proxy: count distinct event types in audit log
    try:
        actions = (
            db.query(func.count(func.distinct(AuditLog.action)))
            .filter(
                AuditLog.organization_id == str(oid),
                AuditLog.created_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )
    except Exception:
        actions = 0
    engagement_score += min(20, actions * 2)

    total = min(100, activity_score + commercial_score + engagement_score)
    return total
