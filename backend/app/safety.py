"""Safety defaults that every module must respect. Tests pin these."""
from . import registry

CRISIS_RESOURCES = (
    {"id": "988", "label": "988 Suicide & Crisis Lifeline (call or text)", "tel": "tel:988", "sms": "sms:988"},
    {"id": "911", "label": "Emergency: 911", "tel": "tel:911"},
)


def crisis_payload(app_name: str) -> dict:
    return {"app": app_name, "resources": list(CRISIS_RESOURCES), "always_available": True}


# Fields that never leave the server in a payload about another member.
# welcome_display_name is consent-gated: it may only ever surface through the
# member's own record or the sanitized welcome feed (app/welcome.py), never
# in a generic member payload.
PRIVATE_MEMBER_FIELDS = {"phone", "email", "password_hash", "identities", "google_sub", "vault_key", "legal_name", "address", "dob", "case_number", "welcome_display_name",
                         # Billing internals (app/billing.py): Stripe linkage and
                         # plan bookkeeping never appear in a member payload.
                         "stripe_customer_id", "stripe_subscription_id", "billing_tier", "plan_selected", "paid_at"}


def public_member(user: dict) -> dict:
    """What other members may see. Phone numbers are never exposed (peer messaging rule)."""
    return {k: v for k, v in user.items() if k not in PRIVATE_MEMBER_FIELDS and k != "_id"}


def public_post(post: dict) -> dict:
    """Anonymous posts are really anonymous to other members: no author id, handle or avatar."""
    out = {k: v for k, v in post.items() if k != "_id"}
    if out.get("anonymous"):
        for key in ("author_id", "author", "author_handle", "author_avatar", "location"):
            out.pop(key, None)
        out["author"] = {"display": "Anonymous"}
    return out


def can_be_hidden(feature_id: str) -> bool:
    """Locks and filters may hide a feature only if it isn't lock-exempt (crisis, relapse, safe-call, wipe)."""
    return feature_id not in registry.lock_exempt_ids()
