"""
PATHS Backend — Billing & Subscription API.

Endpoints:
  GET  /billing/plans               — public plan list (also served at /public/plans)
  GET  /billing/subscription        — org's current subscription
  GET  /billing/invoices            — org's invoice history
  GET  /billing/usage               — org's current usage counters
  POST /billing/checkout-session    — start Stripe Checkout → redirect URL
  POST /billing/customer-portal     — open Stripe Customer Portal → redirect URL
  POST /stripe/webhook              — Stripe event handler

PATHS-121 / PATHS-122 / PATHS-123 (Phase 6)
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.database import get_db
from app.db.models.billing import (
    Invoice,
    Plan,
    Subscription,
    StripeProcessedEvent,
    UsageCounter,
)
from app.db.models.analytics_events import AnalyticsEvent

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["Billing"])

# ── Pydantic schemas ──────────────────────────────────────────────────────────


class PlanOut(BaseModel):
    id: str
    name: str
    code: str
    price_monthly_cents: int
    price_annual_cents: int
    currency: str
    limits: dict
    features: list
    is_public: bool
    stripe_price_id_monthly: str | None
    stripe_price_id_annual: str | None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_obj(cls, p: Plan) -> "PlanOut":
        return cls(
            id=str(p.id),
            name=p.name,
            code=p.code,
            price_monthly_cents=p.price_monthly_cents,
            price_annual_cents=p.price_annual_cents,
            currency=p.currency,
            limits=p.limits or {},
            features=p.features or [],
            is_public=p.is_public,
            stripe_price_id_monthly=p.stripe_price_id_monthly,
            stripe_price_id_annual=p.stripe_price_id_annual,
        )


class SubscriptionOut(BaseModel):
    id: str
    org_id: str
    plan: PlanOut | None
    billing_cycle: str
    status: str
    trial_ends_at: str | None
    current_period_start: str | None
    current_period_end: str | None
    cancel_at_period_end: bool


class InvoiceOut(BaseModel):
    id: str
    amount_cents: int
    currency: str
    status: str
    pdf_url: str | None
    period_start: str | None
    period_end: str | None
    paid_at: str | None
    stripe_invoice_id: str | None


class UsageOut(BaseModel):
    org_id: str
    period_start: str | None
    period_end: str | None
    cvs_processed: int
    jobs_active: int
    agent_runs: int
    seats_used: int


class CheckoutRequest(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"  # monthly | annual


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_org_id_from_request(request: Request) -> str | None:
    """Extract org_id from query param or header (best-effort)."""
    return (
        request.query_params.get("org_id")
        or request.headers.get("X-Org-Id")
    )


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ── Plan list ─────────────────────────────────────────────────────────────────


@router.get("/billing/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """Return all public plans. Used by the /pricing page."""
    plans = db.query(Plan).filter(Plan.is_public.is_(True)).all()
    return [PlanOut.from_orm_obj(p) for p in plans]


# ── Current subscription ──────────────────────────────────────────────────────


@router.get("/billing/subscription", response_model=SubscriptionOut | None)
def get_subscription(org_id: str, db: Session = Depends(get_db)):
    sub = (
        db.query(Subscription)
        .filter(Subscription.org_id == uuid.UUID(org_id))
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub:
        return None
    plan_out = PlanOut.from_orm_obj(sub.plan) if sub.plan else None
    return SubscriptionOut(
        id=str(sub.id),
        org_id=str(sub.org_id),
        plan=plan_out,
        billing_cycle=sub.billing_cycle,
        status=sub.status,
        trial_ends_at=_iso(sub.trial_ends_at),
        current_period_start=_iso(sub.current_period_start),
        current_period_end=_iso(sub.current_period_end),
        cancel_at_period_end=sub.cancel_at_period_end,
    )


# ── Invoices ──────────────────────────────────────────────────────────────────


@router.get("/billing/invoices", response_model=list[InvoiceOut])
def list_invoices(org_id: str, db: Session = Depends(get_db)):
    invoices = (
        db.query(Invoice)
        .filter(Invoice.org_id == uuid.UUID(org_id))
        .order_by(Invoice.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        InvoiceOut(
            id=str(inv.id),
            amount_cents=inv.amount_cents,
            currency=inv.currency,
            status=inv.status,
            pdf_url=inv.pdf_url,
            period_start=_iso(inv.period_start),
            period_end=_iso(inv.period_end),
            paid_at=_iso(inv.paid_at),
            stripe_invoice_id=inv.stripe_invoice_id,
        )
        for inv in invoices
    ]


# ── Usage counters ────────────────────────────────────────────────────────────


@router.get("/billing/usage", response_model=UsageOut)
def get_usage(org_id: str, db: Session = Depends(get_db)):
    counter = (
        db.query(UsageCounter)
        .filter(UsageCounter.org_id == uuid.UUID(org_id))
        .order_by(UsageCounter.period_start.desc())
        .first()
    )
    if not counter:
        return UsageOut(
            org_id=org_id,
            period_start=None,
            period_end=None,
            cvs_processed=0,
            jobs_active=0,
            agent_runs=0,
            seats_used=0,
        )
    return UsageOut(
        org_id=org_id,
        period_start=_iso(counter.period_start),
        period_end=_iso(counter.period_end),
        cvs_processed=counter.cvs_processed,
        jobs_active=counter.jobs_active,
        agent_runs=counter.agent_runs,
        seats_used=counter.seats_used,
    )


# ── Checkout session ──────────────────────────────────────────────────────────


@router.post("/billing/checkout-session", response_model=CheckoutResponse)
def create_checkout_session(
    body: CheckoutRequest,
    org_id: str,
    db: Session = Depends(get_db),
):
    plan = db.query(Plan).filter(Plan.code == body.plan_code).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    price_id = (
        plan.stripe_price_id_annual
        if body.billing_cycle == "annual"
        else plan.stripe_price_id_monthly
    )
    if not price_id:
        raise HTTPException(
            status_code=422,
            detail="No Stripe price configured for this plan/cycle. "
                   "Set stripe_price_id_monthly/annual in the Plan row.",
        )

    # Find or create Stripe customer
    sub = (
        db.query(Subscription)
        .filter(Subscription.org_id == uuid.UUID(org_id))
        .order_by(Subscription.created_at.desc())
        .first()
    )
    customer_id = sub.stripe_customer_id if sub else None
    if not customer_id:
        # Create a new customer on the fly
        try:
            from app.services.stripe_billing import create_customer
            customer_id = create_customer(org_id=org_id, email="", name="")
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Stripe unavailable: {exc}")

    try:
        from app.services.stripe_billing import create_checkout_session as _checkout
        url = _checkout(
            customer_id=customer_id,
            price_id=price_id,
            success_url=f"{settings.app_frontend_url}/billing?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.app_frontend_url}/pricing",
            metadata={"org_id": org_id, "plan_code": body.plan_code},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Stripe checkout failed: {exc}")

    return CheckoutResponse(checkout_url=url)


# ── Customer portal ───────────────────────────────────────────────────────────


@router.post("/billing/customer-portal", response_model=PortalResponse)
def customer_portal(org_id: str, db: Session = Depends(get_db)):
    sub = (
        db.query(Subscription)
        .filter(Subscription.org_id == uuid.UUID(org_id))
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found for this organisation.",
        )
    try:
        from app.services.stripe_billing import create_customer_portal_session
        url = create_customer_portal_session(
            customer_id=sub.stripe_customer_id,
            return_url=f"{settings.app_frontend_url}/billing",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Stripe portal unavailable: {exc}")

    return PortalResponse(portal_url=url)


# ── Stripe Webhook ────────────────────────────────────────────────────────────


@router.post("/stripe/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Receive and process Stripe webhook events.

    Idempotent: events already in stripe_processed_events are silently skipped.
    """
    payload = await request.body()

    # Verify signature
    try:
        from app.services.stripe_billing import construct_webhook_event
        event = construct_webhook_event(payload=payload, sig_header=stripe_signature or "")
    except Exception as exc:
        logger.warning("Stripe webhook signature invalid: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_id: str = event["id"]
    event_type: str = event["type"]

    # Idempotency check
    already = db.get(StripeProcessedEvent, event_id)
    if already:
        return {"status": "already_processed"}

    try:
        _handle_stripe_event(event, db)
    except Exception as exc:
        logger.error("Error handling Stripe event %s (%s): %s", event_id, event_type, exc)
        # Do NOT raise — Stripe will retry, but we acknowledge receipt.

    # Mark processed
    db.add(StripeProcessedEvent(stripe_event_id=event_id))
    db.commit()
    return {"status": "ok"}


def _handle_stripe_event(event: Any, db: Session) -> None:
    """Route a verified Stripe event to the appropriate handler."""
    event_type: str = event["type"]
    data: dict = event["data"]["object"]

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        _sync_subscription(data, db)
    elif event_type == "customer.subscription.deleted":
        _cancel_local_subscription(data, db)
    elif event_type == "invoice.paid":
        _mark_invoice_paid(data, db)
        _emit_analytics(data.get("customer", ""), "billing.payment_succeeded", db)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data, db)
        _emit_analytics(data.get("customer", ""), "billing.payment_failed", db)
    elif event_type == "invoice.created":
        _upsert_invoice(data, db)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)


def _sync_subscription(data: dict, db: Session) -> None:
    stripe_sub_id: str = data.get("id", "")
    stripe_customer_id: str = data.get("customer", "")
    status: str = data.get("status", "active")

    sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )
    if sub:
        sub.status = status
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
        db.flush()


def _cancel_local_subscription(data: dict, db: Session) -> None:
    stripe_sub_id: str = data.get("id", "")
    sub = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == stripe_sub_id)
        .first()
    )
    if sub:
        sub.status = "cancelled"
        db.flush()


def _upsert_invoice(data: dict, db: Session) -> None:
    stripe_invoice_id: str = data.get("id", "")
    if not stripe_invoice_id:
        return
    existing = (
        db.query(Invoice)
        .filter(Invoice.stripe_invoice_id == stripe_invoice_id)
        .first()
    )
    if not existing:
        # Best-effort; we may not have the org_id here. Skip gracefully.
        pass


def _mark_invoice_paid(data: dict, db: Session) -> None:
    stripe_invoice_id: str = data.get("id", "")
    inv = (
        db.query(Invoice)
        .filter(Invoice.stripe_invoice_id == stripe_invoice_id)
        .first()
    )
    if inv:
        inv.status = "paid"
        inv.paid_at = datetime.utcnow()
        db.flush()


def _handle_payment_failed(data: dict, db: Session) -> None:
    # Find the subscription and set past_due
    stripe_sub_id: str = data.get("subscription", "")
    if stripe_sub_id:
        sub = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub_id)
            .first()
        )
        if sub:
            sub.status = "past_due"
            db.flush()


def _emit_analytics(stripe_customer_id: str, event_type: str, db: Session) -> None:
    try:
        db.add(AnalyticsEvent(
            event_type=event_type,
            properties={"stripe_customer_id": stripe_customer_id},
        ))
        db.flush()
    except Exception as exc:
        logger.warning("Could not emit analytics event: %s", exc)
