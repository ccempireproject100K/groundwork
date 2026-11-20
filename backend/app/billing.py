"""Paid plan billing through Stripe Checkout (subscription mode) and a webhook.

Rules this module keeps:
- The plan, price, currency and interval come from app/tiers.py only. The
  client never supplies a tier, an amount or a return URL.
- A member's tier becomes "paid" ONLY inside the webhook, after the Stripe
  signature is verified on the raw bytes and the checkout session's amount and
  currency match the price in tiers.py. Creating a checkout session changes
  nothing.
- Fails closed: without GW_STRIPE_SECRET_KEY and GW_STRIPE_WEBHOOK_SECRET the
  endpoints answer 503 and grant nothing.
- Each Stripe event id is processed at most once (collection stripe_events).
- Stripe is reached over its HTTP API with httpx. Tests swap HTTP_TRANSPORT
  (an httpx.MockTransport) and sign fake events with the same HMAC scheme.
- Keys are read from Settings (environment) and are never logged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from pymongo.errors import DuplicateKeyError

from . import tiers, welcome

log = logging.getLogger("groundwork.billing")

STRIPE_API = "https://api.stripe.com/v1"
PAID_TIER = "paid"
CURRENCY = "usd"
INTERVAL = "month"
SIGNATURE_TOLERANCE_SECONDS = 300
EVENTS_COLLECTION = "stripe_events"
# Subscription states that end the paid plan. Other states (active, trialing,
# past_due, incomplete) never grant anything on their own.
ENDED_STATUSES = ("canceled", "unpaid", "incomplete_expired")

# Tests set this to an httpx.MockTransport so no real Stripe call is made.
HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None


class BillingNotConfigured(Exception):
    """Stripe keys or the public URL are not set; the router answers 503."""


class StripeError(Exception):
    """Stripe answered with an error status (the body is not logged)."""


class SignatureError(Exception):
    """The Stripe-Signature header is missing, malformed, stale or wrong."""


# ---------------- configuration ----------------

def configured(settings) -> bool:
    return bool((settings.stripe_secret_key or "").strip() and (settings.stripe_webhook_secret or "").strip())


def plan() -> dict:
    """The one purchasable plan, read from tiers.py. Never invented here."""
    price = tiers.PLANS[PAID_TIER]["price_cents"]
    if not isinstance(price, int) or price <= 0:
        raise BillingNotConfigured("the paid plan has no price set")
    return {"tier": PAID_TIER, "name": tiers.PLANS[PAID_TIER]["name"], "price_cents": price,
            "currency": CURRENCY, "interval": INTERVAL}


def return_urls(settings) -> tuple[str, str]:
    """Success and cancel URLs, built from GW_PUBLIC_URL only."""
    base = (settings.public_url or "").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise BillingNotConfigured("GW_PUBLIC_URL is not set")
    return f"{base}/settings?checkout=success", f"{base}/settings?checkout=cancelled"


# ---------------- Stripe HTTP API ----------------

def flatten(params: dict, prefix: str = "") -> dict:
    """Nested dict/list -> Stripe's bracketed form fields."""
    out: dict[str, str] = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten(value, name))
        elif isinstance(value, (list, tuple)):
            out.update(flatten({str(i): v for i, v in enumerate(value)}, name))
        elif value is not None:
            out[name] = str(value).lower() if isinstance(value, bool) else str(value)
    return out


async def stripe_post(settings, path: str, params: dict) -> dict:
    headers = {"Authorization": f"Bearer {settings.stripe_secret_key}"}
    async with httpx.AsyncClient(base_url=STRIPE_API, timeout=15.0, transport=HTTP_TRANSPORT) as client:
        resp = await client.post(path, data=flatten(params), headers=headers)
    if resp.status_code >= 400:
        raise StripeError(f"stripe returned {resp.status_code}")
    return resp.json()


async def create_checkout_session(settings, user: dict) -> dict:
    """A subscription-mode Checkout Session for the paid plan. Changes no
    member state: the tier is granted only by the webhook."""
    if not configured(settings):
        raise BillingNotConfigured("billing is not configured")
    p = plan()
    success_url, cancel_url = return_urls(settings)
    meta = {"user_id": user["_id"], "tier": p["tier"]}
    params = {
        "mode": "subscription",
        "client_reference_id": user["_id"],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items": [{
            "quantity": 1,
            "price_data": {
                "currency": p["currency"],
                "unit_amount": p["price_cents"],
                "recurring": {"interval": p["interval"]},
                "product_data": {"name": f"{settings.app_name} {p['name']}"},
            },
        }],
        "metadata": meta,
        "subscription_data": {"metadata": meta},
    }
    return await stripe_post(settings, "/checkout/sessions", params)


# ---------------- webhook signature ----------------

def verify_signature(raw: bytes, header: str | None, secret: str, *, now: float | None = None,
                     tolerance: int = SIGNATURE_TOLERANCE_SECONDS) -> None:
    """Stripe-Signature: t=<unix>,v1=<hex hmac-sha256 of "t.payload">.
    Verified on the raw bytes, constant-time, with a timestamp tolerance."""
    if not secret:
        raise SignatureError("no signing secret")
    if not header:
        raise SignatureError("missing signature")
    timestamp = None
    candidates: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            candidates.append(value)
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        raise SignatureError("bad timestamp") from None
    if not candidates:
        raise SignatureError("no v1 signature")
    signed = str(ts).encode() + b"." + raw
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, c) for c in candidates):
        raise SignatureError("signature mismatch")
    if abs((time.time() if now is None else now) - ts) > tolerance:
        raise SignatureError("timestamp outside tolerance")


# ---------------- event handling ----------------

async def claim_event(db, event_id: str, event_type: str) -> bool:
    """Record the event id. False when it was already processed."""
    try:
        await db[EVENTS_COLLECTION].insert_one({
            "_id": event_id, "type": event_type, "user_id": None,
            "received_at": datetime.now(timezone.utc).isoformat()})
    except DuplicateKeyError:
        return False
    return True


async def release_event(db, event_id: str) -> None:
    """Forget a claim whose handler failed, so Stripe's retry is processed."""
    await db[EVENTS_COLLECTION].delete_one({"_id": event_id})


async def _grant_paid(db, session: dict) -> tuple[str, str | None]:
    """checkout.session.completed -> tier paid, after cross-checks."""
    p = plan()
    meta = session.get("metadata") or {}
    uid = meta.get("user_id")
    ref = session.get("client_reference_id")
    if (session.get("mode") != "subscription" or session.get("payment_status") != "paid"
            or not uid or (ref and ref != uid) or meta.get("tier") != p["tier"]
            or not session.get("subscription")):
        log.warning("checkout session %s rejected: not a paid subscription for this plan", session.get("id"))
        return "rejected", uid
    if (session.get("amount_total") != p["price_cents"]
            or str(session.get("currency") or "").lower() != p["currency"]):
        log.warning("checkout session %s rejected: amount or currency differs from the plan", session.get("id"))
        return "rejected", uid
    user = await db.users.find_one({"_id": uid})
    if not user:
        return "ignored", uid
    customer = session.get("customer")
    await db.users.update_one({"_id": uid}, {"$set": {
        "tier": p["tier"],
        "billing_status": "active",
        "stripe_customer_id": customer if isinstance(customer, str) else None,
        "stripe_subscription_id": session["subscription"] if isinstance(session["subscription"], str) else None,
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }})
    # Deduped per member, so a retried event cannot announce twice.
    await welcome.note_payment_collected(db, uid)
    return "granted", uid


async def _end_paid(db, sub: dict) -> tuple[str, str | None]:
    """A subscription ended -> tier free. Only the member's current
    subscription can end their plan."""
    sub_id = sub.get("id")
    user = await db.users.find_one({"stripe_subscription_id": sub_id}) if sub_id else None
    if user is None:
        uid = (sub.get("metadata") or {}).get("user_id")
        candidate = await db.users.find_one({"_id": uid}) if uid else None
        if candidate is not None and not candidate.get("stripe_subscription_id"):
            user = candidate
    if user is None:
        return "ignored", None
    await db.users.update_one({"_id": user["_id"]}, {"$set": {
        "tier": "free", "billing_status": sub.get("status") or "canceled"}})
    return "downgraded", user["_id"]


async def handle_event(db, event: dict) -> tuple[str, str | None]:
    """Returns (outcome, user_id). Unknown event types are ignored."""
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if etype == "checkout.session.completed":
        return await _grant_paid(db, obj)
    if etype == "customer.subscription.deleted":
        return await _end_paid(db, obj)
    if etype == "customer.subscription.updated" and obj.get("status") in ENDED_STATUSES:
        return await _end_paid(db, obj)
    return "ignored", None


async def process_webhook(db, raw: bytes) -> dict:
    """Parse a verified payload and process it once."""
    try:
        event = json.loads(raw)
        event_id = event["id"]
        event_type = event["type"]
        if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
            raise ValueError("bad event")
    except (ValueError, KeyError, TypeError):
        raise ValueError("malformed event") from None
    if not await claim_event(db, event_id, event_type):
        return {"received": True, "duplicate": True}
    try:
        outcome, uid = await handle_event(db, event)
    except Exception:
        await release_event(db, event_id)
        raise
    await db[EVENTS_COLLECTION].update_one({"_id": event_id}, {"$set": {"user_id": uid, "outcome": outcome}})
    return {"received": True, "outcome": outcome}


def status_view(settings, user: dict) -> dict:
    try:
        p = plan()
    except BillingNotConfigured:
        p = None
    return {"configured": configured(settings) and bool((settings.public_url or "").strip()),
            "tier": user.get("tier", "free"), "plan": p,
            "subscription_status": user.get("billing_status")}
