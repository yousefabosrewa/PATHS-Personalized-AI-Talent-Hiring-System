"""
PATHS Backend — Stripe billing service.

Wraps the Stripe Python SDK so the rest of the app never imports stripe directly.
All amounts are in the lowest currency unit (cents for USD).

PATHS-121 (Phase 6 — Commercial Launch)
"""

from __future__ import annotations

from typing import Any
import uuid

try:
    import stripe as _stripe
    _stripe_available = True
except ImportError:
    _stripe_available = False

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _sdk() -> Any:
    """Return a lazily initialised stripe module, or raise if not installed."""
    if not _stripe_available:
        raise RuntimeError(
            "stripe package is not installed. "
            "Add `stripe` to requirements.txt and reinstall."
        )
    _stripe.api_key = settings.stripe_secret_key or ""
    return _stripe


# ── Customer ──────────────────────────────────────────────────────────────────

def create_customer(org_id: str | uuid.UUID, email: str, name: str) -> str:
    """Create a Stripe customer for an organisation and return the customer id."""
    sdk = _sdk()
    customer = sdk.Customer.create(
        email=email,
        name=name,
        metadata={"org_id": str(org_id)},
    )
    logger.info("Stripe customer created: %s for org %s", customer.id, org_id)
    return customer.id


# ── Subscription ──────────────────────────────────────────────────────────────

def create_subscription(
    customer_id: str,
    price_id: str,
    trial_days: int = 14,
) -> dict[str, Any]:
    """
    Create a Stripe subscription with an optional trial period.

    Returns ``{sub_id, status, trial_end}``.
    """
    sdk = _sdk()
    kwargs: dict[str, Any] = {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "payment_behavior": "default_incomplete",
        "payment_settings": {"save_default_payment_method": "on_subscription"},
        "expand": ["latest_invoice.payment_intent"],
    }
    if trial_days:
        kwargs["trial_period_days"] = trial_days

    sub = sdk.Subscription.create(**kwargs)
    return {
        "sub_id": sub.id,
        "status": sub.status,
        "trial_end": sub.trial_end,
        "client_secret": (
            sub.latest_invoice.payment_intent.client_secret
            if sub.latest_invoice and sub.latest_invoice.payment_intent
            else None
        ),
    }


def update_subscription_plan(
    stripe_sub_id: str,
    new_price_id: str,
) -> dict[str, Any]:
    """Move an existing subscription to a different price."""
    sdk = _sdk()
    sub = sdk.Subscription.retrieve(stripe_sub_id)
    item_id = sub["items"]["data"][0]["id"]
    updated = sdk.Subscription.modify(
        stripe_sub_id,
        items=[{"id": item_id, "price": new_price_id}],
        proration_behavior="create_prorations",
    )
    return {"sub_id": updated.id, "status": updated.status}


def cancel_subscription(stripe_sub_id: str, at_period_end: bool = True) -> dict[str, Any]:
    """Cancel a subscription, optionally at end of current period."""
    sdk = _sdk()
    if at_period_end:
        sub = sdk.Subscription.modify(stripe_sub_id, cancel_at_period_end=True)
    else:
        sub = sdk.Subscription.cancel(stripe_sub_id)
    return {"sub_id": sub.id, "status": sub.status}


# ── Checkout ──────────────────────────────────────────────────────────────────

def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str] | None = None,
) -> str:
    """Create a Stripe Checkout Session and return the session URL."""
    sdk = _sdk()
    session = sdk.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return session.url


# ── Customer portal ───────────────────────────────────────────────────────────

def create_customer_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session URL."""
    sdk = _sdk()
    session = sdk.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


# ── Webhook verification ──────────────────────────────────────────────────────

def construct_webhook_event(payload: bytes, sig_header: str) -> Any:
    """
    Verify and parse an incoming Stripe webhook.

    Raises ``stripe.error.SignatureVerificationError`` on invalid signature.
    """
    sdk = _sdk()
    return sdk.Webhook.construct_event(
        payload=payload,
        sig_header=sig_header,
        secret=settings.stripe_webhook_secret or "",
    )
