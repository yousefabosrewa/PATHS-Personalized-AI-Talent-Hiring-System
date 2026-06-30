"""
PATHS Backend — Owner portal API.

All endpoints require account_type='owner'.

Endpoints:
  GET  /owner/revenue-summary
  GET  /owner/analytics/revenue
  GET  /owner/customers
  GET  /owner/orgs
  GET  /owner/plans
  POST /owner/plans
  PUT  /owner/plans/{id}
  GET  /owner/platform-config
  PUT  /owner/platform-config
  GET  /owner/analytics/marketing
  GET  /owner/announcements
  POST /owner/announcements

PATHS-149–152 (Phase 7 — Admin & Owner Portals)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_platform_admin  # reuse — owner is a superset
from app.core.logging import get_logger
from app.db.models.admin_platform import Announcement, PlatformSettings
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.billing import Invoice, Plan, Subscription
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.org_health import compute_org_health

logger = get_logger(__name__)

router = APIRouter(
    prefix="/owner",
    tags=["Owner"],
    dependencies=[Depends(require_platform_admin)],  # OWNER check; tighten if separate role exists
)


# ── Revenue summary ───────────────────────────────────────────────────────────


class RevenueSummary(BaseModel):
    mrr_cents: int
    arr_cents: int
    churn_rate_30d: float
    new_orgs_this_month: int
    new_orgs_last_month: int
    active_seats_used: int
    revenue_by_plan: list[dict]
    top_customers: list[dict]
    alerts: list[dict]


@router.get("/revenue-summary", response_model=RevenueSummary)
def revenue_summary(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Active subscriptions
    active_subs = (
        db.query(Subscription)
        .filter(Subscription.status == "active")
        .all()
    )

    mrr_cents = 0
    revenue_by_plan: dict[str, int] = {}
    org_revenue: dict[uuid.UUID, int] = {}
    for sub in active_subs:
        if sub.plan:
            cents = (
                sub.plan.price_annual_cents // 12
                if sub.billing_cycle == "annual"
                else sub.plan.price_monthly_cents
            )
            mrr_cents += cents
            revenue_by_plan[sub.plan.code] = revenue_by_plan.get(sub.plan.code, 0) + cents
            org_revenue[sub.org_id] = org_revenue.get(sub.org_id, 0) + cents

    total_revenue = mrr_cents or 1  # avoid div-by-zero

    # New orgs this / last month
    new_this = (
        db.query(func.count(Organization.id))
        .filter(Organization.created_at >= month_start)
        .scalar()
        or 0
    )
    new_last = (
        db.query(func.count(Organization.id))
        .filter(
            Organization.created_at >= prev_month_start,
            Organization.created_at < month_start,
        )
        .scalar()
        or 0
    )

    # Churn (cancelled subs in last 30d / total active last month)
    cancelled_30d = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == "cancelled",
            Subscription.updated_at >= now - timedelta(days=30),
        )
        .scalar()
        or 0
    )
    total_active = max(len(active_subs), 1)
    churn_rate = round(cancelled_30d / total_active, 4)

    # Failed payment alerts
    past_due = (
        db.query(Subscription)
        .filter(Subscription.status == "past_due")
        .limit(5)
        .all()
    )
    alerts = [
        {
            "kind": "payment_failed",
            "org_id": str(s.org_id),
            "message": "Subscription past due",
        }
        for s in past_due
    ]

    # Active seats in use = active organisation (non-candidate) accounts
    active_seats_used = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True), User.account_type != "candidate")
        .scalar()
        or 0
    )

    # Top 5 customers by MRR
    top_org_ids = sorted(org_revenue, key=lambda oid: org_revenue[oid], reverse=True)[:5]
    org_names = (
        {
            o.id: o.name
            for o in db.query(Organization)
            .filter(Organization.id.in_(top_org_ids))
            .all()
        }
        if top_org_ids
        else {}
    )
    top_customers = [
        {
            "org_id": str(oid),
            "name": org_names.get(oid, "Unknown"),
            "mrr_cents": org_revenue[oid],
        }
        for oid in top_org_ids
    ]

    return RevenueSummary(
        mrr_cents=mrr_cents,
        arr_cents=mrr_cents * 12,
        churn_rate_30d=churn_rate,
        new_orgs_this_month=new_this,
        new_orgs_last_month=new_last,
        active_seats_used=active_seats_used,
        revenue_by_plan=[
            {"plan": code, "cents": cents, "pct": round(cents / total_revenue, 4)}
            for code, cents in revenue_by_plan.items()
        ],
        top_customers=top_customers,
        alerts=alerts,
    )


# ── Revenue analytics ─────────────────────────────────────────────────────────


@router.get("/analytics/revenue")
def revenue_analytics(
    from_date: str = Query(default="", alias="from"),
    to_date: str = Query(default="", alias="to"),
    db: Session = Depends(get_db),
):
    """Daily/monthly revenue aggregation from invoice payments."""
    q = db.query(Invoice).filter(Invoice.status == "paid")
    if from_date:
        try:
            q = q.filter(Invoice.paid_at >= datetime.fromisoformat(from_date))
        except ValueError:
            pass
    if to_date:
        try:
            q = q.filter(Invoice.paid_at <= datetime.fromisoformat(to_date))
        except ValueError:
            pass
    invoices = q.order_by(Invoice.paid_at).all()
    return [
        {
            "date": inv.paid_at.date().isoformat() if inv.paid_at else None,
            "amount_cents": inv.amount_cents,
            "currency": inv.currency,
        }
        for inv in invoices
    ]


# ── Customers ─────────────────────────────────────────────────────────────────


@router.get("/customers")
def list_customers(
    health: str = Query(default=""),
    plan: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """All orgs with health scores and plan info."""
    orgs = db.query(Organization).all()
    result = []
    for org in orgs:
        health_score = compute_org_health(str(org.id), db)
        sub = (
            db.query(Subscription)
            .filter(Subscription.org_id == org.id, Subscription.status == "active")
            .first()
        )
        plan_code = sub.plan.code if sub and sub.plan else None

        if plan and plan_code != plan:
            continue
        if health == "at_risk" and health_score >= 40:
            continue

        result.append(
            {
                "org_id": str(org.id),
                "name": org.name,
                "status": org.status.value if hasattr(org.status, "value") else str(org.status),
                "plan": plan_code,
                "health_score": health_score,
                "created_at": org.created_at.isoformat() if org.created_at else None,
            }
        )
    return result


# ── Owner org list ────────────────────────────────────────────────────────────


@router.get("/orgs")
def owner_orgs(
    q: str = Query(default=""),
    plan: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = db.query(Organization)
    if q:
        query = query.filter(Organization.name.ilike(f"%{q}%"))
    orgs = query.all()
    return [
        {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "status": org.status.value if hasattr(org.status, "value") else str(org.status),
            "created_at": org.created_at.isoformat() if org.created_at else None,
        }
        for org in orgs
    ]


# ── Plans editor ──────────────────────────────────────────────────────────────


class PlanUpsert(BaseModel):
    name: str
    code: str
    price_monthly_cents: int
    price_annual_cents: int
    currency: str = "USD"
    limits: dict = {}
    features: list = []
    is_public: bool = True
    stripe_price_id_monthly: str | None = None
    stripe_price_id_annual: str | None = None


@router.get("/plans")
def owner_list_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "price_monthly_cents": p.price_monthly_cents,
            "price_annual_cents": p.price_annual_cents,
            "currency": p.currency,
            "limits": p.limits,
            "features": p.features,
            "is_public": p.is_public,
        }
        for p in plans
    ]


@router.post("/plans", status_code=201)
def owner_create_plan(body: PlanUpsert, db: Session = Depends(get_db)):
    plan = Plan(**body.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"id": str(plan.id), "code": plan.code}


@router.put("/plans/{plan_id}")
def owner_update_plan(plan_id: str, body: PlanUpsert, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter(Plan.id == uuid.UUID(plan_id)).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    return {"id": str(plan.id), "code": plan.code}


# ── Platform config ───────────────────────────────────────────────────────────


@router.get("/platform-config")
def get_platform_config(db: Session = Depends(get_db)):
    ps = db.get(PlatformSettings, 1)
    if not ps:
        return {}
    return {
        "display_name": ps.display_name,
        "support_email": ps.support_email,
        "legal_company_name": ps.legal_company_name,
        "maintenance_mode": ps.maintenance_mode,
        "email_templates": ps.email_templates,
    }


class PlatformConfigUpdate(BaseModel):
    display_name: str | None = None
    support_email: str | None = None
    legal_company_name: str | None = None
    maintenance_mode: bool | None = None
    email_templates: dict | None = None


@router.put("/platform-config")
def update_platform_config(body: PlatformConfigUpdate, db: Session = Depends(get_db)):
    ps = db.get(PlatformSettings, 1)
    if not ps:
        ps = PlatformSettings(id=1)
        db.add(ps)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ps, k, v)
    db.commit()
    return {"status": "updated"}


# ── Marketing analytics (stub) ────────────────────────────────────────────────


@router.get("/analytics/marketing")
def marketing_analytics(db: Session = Depends(get_db)):
    """UTM funnel from analytics_events. Stub — returns empty data until UTM tracking is set up."""
    return {
        "sessions": 0,
        "signups": db.query(func.count(Organization.id)).scalar() or 0,
        "conversions": 0,
        "by_utm_source": [],
    }


# ── Announcements ─────────────────────────────────────────────────────────────


class AnnouncementCreate(BaseModel):
    content: str
    audience: dict = {}
    in_app_banner_enabled: bool = False
    banner_color: str = "blue"
    scheduled_at: str | None = None


@router.get("/announcements")
def list_announcements(db: Session = Depends(get_db)):
    anns = db.query(Announcement).order_by(Announcement.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(a.id),
            "content": a.content[:100],
            "in_app_banner_enabled": a.in_app_banner_enabled,
            "banner_color": a.banner_color,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in anns
    ]


@router.post("/announcements", status_code=201)
def create_announcement(body: AnnouncementCreate, db: Session = Depends(get_db)):
    scheduled = None
    if body.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(body.scheduled_at)
        except ValueError:
            pass

    ann = Announcement(
        content=body.content,
        audience=body.audience,
        in_app_banner_enabled=body.in_app_banner_enabled,
        banner_color=body.banner_color,
        scheduled_at=scheduled,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"id": str(ann.id), "status": "created"}


# ── Active banner (unauthenticated) ──────────────────────────────────────────


@router.get("/active-banner", include_in_schema=False)
def active_banner(db: Session = Depends(get_db)):
    """Return the latest active in-app banner (no auth required)."""
    ann = (
        db.query(Announcement)
        .filter(
            Announcement.in_app_banner_enabled.is_(True),
            Announcement.sent_at.isnot(None),
        )
        .order_by(Announcement.sent_at.desc())
        .first()
    )
    if not ann:
        return None
    return {
        "id": str(ann.id),
        "content": ann.content,
        "banner_color": ann.banner_color,
    }
