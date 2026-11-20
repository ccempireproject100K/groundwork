"""Plans and what each includes. Every feature gate reads this file (pattern from Trade Circle's tiers.py).

Prices were set by Brann (free $0; paid $3.99/month, 2026-11-19, the same
prices as Groundwork YEE). There is NO top tier and none may be invented.
Brann assigned every feature to a plan on 2026-11-20, so nothing in the
registry is "unassigned" any more (a test pins that). The paid tier's name
stays "Paid" until he renames it.
"""
from fastapi import HTTPException, status

from . import registry

TIER_ORDER = {"free": 0, "paid": 1}

PLANS = {
    "free": {"name": "Free", "price_cents": 0},
    # price_cents: set by Brann, 2026-11-19, same prices as Groundwork YEE. Never invent another price or a top tier.
    "paid": {"name": "Paid", "price_cents": 399},
}


def features_for(tier: str) -> list[str]:
    return [f.id for f in registry.FEATURES if f.tier == tier]


def unassigned() -> list[str]:
    return [f.id for f in registry.FEATURES if f.tier == "unassigned"]


def plan_table() -> dict:
    return {
        "plans": PLANS,
        "free": features_for("free"),
        "paid": features_for("paid"),
        "unassigned": unassigned(),
    }


def has_access(user_tier: str, feature_id: str) -> bool:
    f = registry.get(feature_id)
    if f.always_free or f.tier == "free":
        return True
    if f.tier == "unassigned":
        return True  # defensive: no feature is unassigned since 2026-11-20
    return TIER_ORDER.get(user_tier, 0) >= TIER_ORDER[f.tier]


def require(user_tier: str, feature_id: str) -> None:
    if not has_access(user_tier, feature_id):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"{feature_id} is on the paid plan")
