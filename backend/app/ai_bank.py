"""The AI bank — the minimal honest meter for paid AI calls.

Shipped with the AI résumé assist (build spec §5.4 in
~/workspace/buildout/ai-resume-builder/REPORT.md). The fuller bank in the
pricing design (free pool -> credits top-up) is still a proposal; this module
is the smallest real version of it — an append-only usage ledger plus a
monthly pool check — shaped so the later ecosystem/credits build extends it
rather than replacing it.

Rules (owner's, 2026-11-01):
- The owner set ONE pool number: 13 cents per member per month for the
  entry tier the résumé assist is earmarked for, sized so his $1-per-member
  profit floor holds exactly ($1.99 - ~36c card fees - 50c referral - 13c
  pool = $1.00). NOTE (2026-11-19): that sizing assumed a $1.99 entry tier;
  the paid tier is now $3.99/month and the owner has not re-sized the pool.
  Per-tier overrides are his slots below; None means "not
  set", and until he sets one the entry pool governs every tier that
  includes the feature. Never invent a pool number.
- Debit is ACTUAL token usage at the published Muse Spark rates, converted
  to cents, rounded up, minimum 1 cent per call.
- The pool is checked BEFORE a call (used + worst case <= pool); when the
  check fails, no call is made. Fail-closed: any ledger error blocks.
"""
import math
from datetime import datetime, timezone

# Published Meta Model API rates for Muse Spark, verified 2026-10-30
# (connector doc): $1.25 / 1M input tokens, $4.25 / 1M output tokens.
INPUT_USD_PER_TOKEN = 1.25 / 1_000_000
OUTPUT_USD_PER_TOKEN = 4.25 / 1_000_000

ENTRY_POOL_CENTS = 13  # owner's figure for the entry tier, 2026-11-01
TIER_POOL_CENTS: dict[str, int | None] = {"paid": None, "top": None}  # owner slots

# Worst-case cost of one call, enforced by the provider's token caps
# (spec §5.4): guided <= ~1.1c, import <= ~1.5c. Pre-flight charges the
# guided/import worst case for the path being attempted.
WORST_CASE_CENTS = {"guided": 2, "import": 2}

POOL_EMPTY_COPY = (
    "You've used this month's AI help for résumé writing. "
    "You can still build or edit a résumé yourself for free — that never stops. "
    "AI help starts again next month."
)


def pool_cents_for(tier: str) -> int:
    override = TIER_POOL_CENTS.get(tier)
    return ENTRY_POOL_CENTS if override is None else override


def cost_cents(input_tokens: int, output_tokens: int) -> int:
    usd = input_tokens * INPUT_USD_PER_TOKEN + output_tokens * OUTPUT_USD_PER_TOKEN
    return max(1, math.ceil(usd * 100))


def _month_start_iso(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def used_this_month_cents(db, user_id: str) -> int:
    """Sum of this calendar month's debits for the member (ledger is truth)."""
    docs = await db.ai_usage.find(
        {"user_id": user_id, "created_at": {"$gte": _month_start_iso()}}
    ).to_list(10000)
    return sum(int(d.get("cents", 0)) for d in docs)


async def check_pool(db, user_id: str, tier: str, path: str) -> dict:
    """Pre-flight: may one more worst-case call be made? Fail-closed."""
    pool = pool_cents_for(tier)
    try:
        used = await used_this_month_cents(db, user_id)
    except Exception:
        return {"ok": False, "pool_cents": pool, "used_cents": pool, "error": "ledger_unavailable"}
    worst = WORST_CASE_CENTS[path]
    return {"ok": used + worst <= pool, "pool_cents": pool, "used_cents": used}


async def debit(db, user_id: str, path: str, usage: dict) -> dict:
    """Append one call's actual cost to the ledger. Append-only: no balances."""
    cents = cost_cents(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))
    doc = {
        "user_id": user_id,
        "feature": "resume_ai_assist",
        "path": path,
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cents": cents,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_usage.insert_one(doc)
    return doc
