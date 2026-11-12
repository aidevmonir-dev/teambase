"""Plans and payment.

With Stripe keys set, upgrading opens Stripe Checkout and the plan changes only when Stripe's signed
webhook confirms the payment. Without keys the app runs in demo billing mode: plan changes apply at
once and the screen says no payment was taken.
"""
from __future__ import annotations

import logging

import stripe
from django.conf import settings

from .models import PLAN_LIMITS, Organization, Plan

log = logging.getLogger(__name__)


class BillingError(Exception):
    """A message that is safe to show the user."""


def stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and all(settings.STRIPE_PRICES.values()))


def plans() -> list[dict]:
    return [
        {"id": plan.value, "name": plan.label, "price_month": PLAN_LIMITS[plan]["price"],
         "seats": PLAN_LIMITS[plan]["seats"], "projects": PLAN_LIMITS[plan]["projects"]}
        for plan in Plan
    ]


def check_fits(org: Organization, plan: str) -> None:
    """Refuse a downgrade the organisation has already outgrown."""
    limits = PLAN_LIMITS[plan]
    if org.seats_used() > limits["seats"]:
        raise BillingError(f"The {Plan(plan).label} plan has {limits['seats']} seats and you use {org.seats_used()}. Remove members or invitations first.")
    if org.projects.count() > limits["projects"]:
        raise BillingError(f"The {Plan(plan).label} plan allows {limits['projects']} projects and you have {org.projects.count()}.")


def plan_for_price(price_id: str) -> str | None:
    for plan, price in settings.STRIPE_PRICES.items():
        if price and price == price_id:
            return plan
    return None


def start_checkout(org: Organization, plan: str, email: str) -> dict:
    """Returns {"url": ...} to send the browser to, or {"changed": True} in demo mode."""
    if plan not in Plan.values:
        raise BillingError("Unknown plan.")
    if plan == org.plan:
        raise BillingError("You are already on this plan.")
    check_fits(org, plan)
    if not stripe_enabled():
        org.plan = plan
        org.save(update_fields=["plan"])
        return {"changed": True, "mode": "demo"}
    if plan == Plan.FREE:
        raise BillingError("To cancel a paid plan, use Manage billing.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    params = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICES[plan], "quantity": 1}],
        "success_url": f"{settings.SITE_URL}/app/billing/?checkout=success",
        "cancel_url": f"{settings.SITE_URL}/app/billing/?checkout=cancelled",
        "client_reference_id": str(org.pk),
        "metadata": {"organization_id": str(org.pk), "plan": plan},
        "subscription_data": {"metadata": {"organization_id": str(org.pk), "plan": plan}},
    }
    if org.stripe_customer_id:
        params["customer"] = org.stripe_customer_id
    else:
        params["customer_email"] = email
    try:
        session = stripe.checkout.Session.create(**params)
    except stripe.StripeError as exc:
        log.error("Stripe checkout failed: %s", exc)
        raise BillingError("The payment provider could not start checkout. Try again shortly.") from exc
    return {"url": session.url, "mode": "stripe"}


def portal(org: Organization) -> dict:
    if not stripe_enabled() or not org.stripe_customer_id:
        raise BillingError("There is no paid subscription to manage.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.billing_portal.Session.create(customer=org.stripe_customer_id, return_url=f"{settings.SITE_URL}/app/billing/")
    except stripe.StripeError as exc:
        log.error("Stripe portal failed: %s", exc)
        raise BillingError("The payment provider is unavailable. Try again shortly.") from exc
    return {"url": session.url}


def handle_event(event) -> str:
    """Apply a verified Stripe event. Returns a short description for the log."""
    kind = event["type"]
    obj = event["data"]["object"]
    meta = obj.get("metadata") or {}
    org = Organization.objects.filter(pk=meta.get("organization_id") or obj.get("client_reference_id") or 0).first()
    if org is None and obj.get("customer"):
        org = Organization.objects.filter(stripe_customer_id=obj["customer"]).first()
    if org is None:
        return f"{kind}: no matching organisation"

    if kind == "checkout.session.completed":
        org.plan = meta.get("plan", org.plan)
        org.stripe_customer_id = obj.get("customer") or org.stripe_customer_id
        org.stripe_subscription_id = obj.get("subscription") or org.stripe_subscription_id
    elif kind == "customer.subscription.updated":
        items = (obj.get("items") or {}).get("data") or []
        plan = plan_for_price(items[0]["price"]["id"]) if items else None
        if plan and obj.get("status") in {"active", "trialing"}:
            org.plan = plan
    elif kind == "customer.subscription.deleted":
        org.plan = Plan.FREE
        org.stripe_subscription_id = ""
    else:
        return f"{kind}: ignored"
    org.save()
    return f"{kind}: {org.name} is on {org.plan}"
