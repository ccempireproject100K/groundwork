"""Paid plan billing: Stripe Checkout, the Stripe webhook, and plan status."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import billing
from ..deps import get_current_user

log = logging.getLogger("groundwork.billing")
router = APIRouter(prefix="/api/billing", tags=["billing"])


def _require_configured(settings) -> None:
    if not billing.configured(settings):
        raise HTTPException(503, "billing is not configured")


@router.post("/checkout")
async def checkout(request: Request, user=Depends(get_current_user)):
    """Start a Stripe Checkout Session for the paid plan. Nothing is granted
    here: the plan is switched on by the verified webhook after payment."""
    settings = request.app.state.settings
    _require_configured(settings)
    if user.get("tier") == billing.PAID_TIER:
        raise HTTPException(409, "already on the paid plan")
    try:
        session = await billing.create_checkout_session(settings, user)
    except billing.BillingNotConfigured:
        raise HTTPException(503, "billing is not configured")
    except Exception as exc:
        log.warning("checkout session could not be created: %s", type(exc).__name__)
        raise HTTPException(502, "payment provider unavailable")
    url = session.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise HTTPException(502, "payment provider unavailable")
    return {"url": url}


@router.post("/webhook")
async def webhook(request: Request):
    settings = request.app.state.settings
    _require_configured(settings)
    raw = await request.body()
    try:
        billing.verify_signature(raw, request.headers.get("Stripe-Signature"), settings.stripe_webhook_secret)
    except billing.SignatureError:
        raise HTTPException(400, "invalid signature")
    try:
        return await billing.process_webhook(request.app.state.db, raw)
    except ValueError:
        raise HTTPException(400, "malformed event")
    except Exception:
        log.exception("stripe webhook handler failed")
        raise HTTPException(500, "webhook handler failed")


@router.get("/status")
async def status(request: Request, user=Depends(get_current_user)):
    return billing.status_view(request.app.state.settings, user)
