"""New-member welcome banner: privacy-first announcements from REAL events.

Settled design (owner spec, Trade Circle welcome-banner handoff, 2026-11-02,
as amended by the owner's final trigger rules, 2026-11-03): there are exactly
TWO announcement triggers, and dedupe is PER ANNOUNCEMENT TYPE — a member can
be announced at most once as free and at most once as paid, ever.

1. FREE trigger — ``note_onboarding_completed()``: fires when BOTH
   (a) a banner opt-in is on file (a ``named`` / ``anonymous`` / ``optout``
   choice), AND (b) onboarding is completed while the member has not yet
   been charged. In this codebase, account creation in Settings IS the
   onboarding: the banner choice is the first fieldset of the account card
   and is sent with registration, so the closest real onboarding-complete
   event is a successful registration carrying a choice. Free entries are
   LABELED: the feed carries ``"free": true`` and the banner renders a
   "Free member" tag next to the name.
2. PAID trigger — ``note_payment_collected()``: fires when BOTH (a) a banner
   opt-in is on file, AND (b) a first payment has actually been COLLECTED.
   It announces EVERY paying member, including members who were already
   free-announced: the paid announcement is a DISTINCT second announcement
   (a conversion event), marked ``"paid": true`` in the feed and carrying
   NO free tag.

   GAP — this hook is intentionally UNCALLED: the paid tier exists only
   in the plan registry (``tiers.py``); no
   payment provider has been chosen or built, and a repo-wide check finds
   no checkout, charge, subscription, webhook, or any other real
   payment-collected event anywhere in this codebase. Nothing may call
   ``note_payment_collected()`` until a real payment flow exists and can
   call it at the moment a first payment is actually collected. Do NOT
   fake a payment event (selecting a paid tier at registration is NOT a
   payment — such a member is uncharged and gets the free announcement).

Choices (onboarding's first question):

- ``named``     — show the member's chosen public display name.
- ``anonymous`` — "a new member joined", no name.
- ``optout``    — no name, ever; the join is celebrated generically as
  "a new customer" with nothing that identifies the person.
- not chosen    — DEFAULT: no announcement at all until the member chooses.

Privacy rules pinned by tests (tests/test_welcome.py):
- Never expose legal names, emails, or phone numbers. The only name that can
  appear is the display name the member typed for this purpose (falling back
  to their public handle only when they explicitly chose ``named``).
- Display names are sanitized: control/HTML characters stripped, whitespace
  collapsed, capped length, and anything email-like, phone-like, or URL-like
  is rejected (the announcement then falls back to anonymous).
- Later opt-outs are honored immediately: switching to ``optout`` strips the
  name from the live announcements in place; switching to "none" removes
  them.
- Real events only: announcements are created solely from the two triggers
  above (the free trigger at registration, the paid trigger at a genuinely
  collected payment) or the member's own later choice change completing
  onboarding. Never on login, never fabricated; an empty feed is honest.
- Capped history: the feed returns at most MAX_FEED entries and storage is
  pruned to MAX_STORED. The feed endpoint sends an HTTP cache header so
  repeat reads are cheap. No paid calls of any kind are made here.
"""
import re
import unicodedata
import uuid
from datetime import datetime, timezone

COLLECTION = "welcome_announcements"

CHOICES = ("named", "anonymous", "optout")
MAX_FEED = 20
MAX_STORED = 50
MAX_NAME_LENGTH = 24
CACHE_MAX_AGE_SECONDS = 30

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_HTML_CHARS = re.compile(r"[<>&\"'`]")
_WHITESPACE = re.compile(r"\s+")
_URL_LIKE = re.compile(r"(https?://|www\.|\.(com|net|org|io|co)\b)", re.IGNORECASE)


def sanitize_display_name(raw) -> str | None:
    """Return a safe public display name, or None if the input is unusable.

    None means: do not show a name (fall back to an anonymous announcement).
    Rejects anything that looks like an email address, a phone number, or a
    URL, so a member cannot accidentally (or maliciously) publish contact
    details in the ticker.
    """
    if not raw or not isinstance(raw, str):
        return None
    if "<" in raw or ">" in raw:
        return None  # markup attempt: reject the name, do not clean-and-show it
    name = unicodedata.normalize("NFKC", raw)
    name = _CONTROL.sub("", name)
    name = _HTML_CHARS.sub("", name)
    name = _WHITESPACE.sub(" ", name).strip()
    if not name:
        return None
    if "@" in name or _URL_LIKE.search(name):
        return None
    digits = sum(ch.isdigit() for ch in name)
    if digits >= 7:  # phone-like, in any grouping
        return None
    return name[:MAX_NAME_LENGTH].strip() or None


def _kind_and_name(choice: str, display_name_raw, fallback_handle: str | None):
    """Map a settled choice to (announcement kind, public name or None)."""
    if choice == "named":
        # A display name the member supplied but that fails safety checks is
        # REJECTED (announcement goes anonymous) — never silently replaced by
        # another identifier. Only when no name was supplied at all may the
        # member's public handle stand in, since "named" was their choice.
        if display_name_raw is not None:
            name = sanitize_display_name(display_name_raw)
        else:
            name = sanitize_display_name(fallback_handle)
        if name:
            return "named", name
        return "anonymous", None  # chose named but gave nothing safe to show
    if choice == "anonymous":
        return "anonymous", None
    return "generic", None  # optout: celebrated generically, never named


def public_announcement(doc: dict) -> dict:
    """The ONLY shape the feed returns: no user_id, no tier, no contact data.

    ``free`` / ``paid`` are the announcement-type labels and are present
    (true) only on entries of that type: a paid entry never carries the
    free tag, and a free entry never carries the paid mark.
    """
    out = {"kind": doc.get("kind", "generic"), "created_at": doc.get("created_at")}
    if doc.get("kind") == "named" and doc.get("display_name"):
        out["display_name"] = doc["display_name"]
    if doc.get("free"):
        out["free"] = True
    if doc.get("paid"):
        out["paid"] = True
    return out


async def _prune(db) -> None:
    count = await db[COLLECTION].count_documents({})
    if count <= MAX_STORED:
        return
    cursor = db[COLLECTION].find({}, {"_id": 1}).sort("created_at", 1).limit(count - MAX_STORED)
    oldest = await cursor.to_list(length=count - MAX_STORED)
    for doc in oldest:
        await db[COLLECTION].delete_one({"_id": doc["_id"]})


async def _find_typed(db, user_id: str, flag: str) -> dict | None:
    """The member's existing announcement of one type (flag: free|paid)."""
    return await db[COLLECTION].find_one({"user_id": user_id, flag: True})


async def _record_announcement(db, user_id: str, choice: str,
                               display_name_raw, fallback_handle: str | None,
                               *, paid: bool) -> dict | None:
    """Create the member's announcement of one type, deduped per type."""
    flag = "paid" if paid else "free"
    existing = await _find_typed(db, user_id, flag)
    if existing:
        return existing
    kind, name = _kind_and_name(choice, display_name_raw, fallback_handle)
    doc = {"_id": uuid.uuid4().hex, "user_id": user_id, "kind": kind,
           "created_at": datetime.now(timezone.utc).isoformat(), flag: True}
    if name:
        doc["display_name"] = name
    await db[COLLECTION].insert_one(doc)
    await _prune(db)
    return doc


async def note_onboarding_completed(db, user_id: str, choice: str | None,
                                    display_name_raw=None, fallback_handle: str | None = None) -> dict | None:
    """FREE trigger: onboarding completed while not yet charged.

    In this codebase the onboarding-complete event IS a successful
    registration carrying a banner choice (account creation in Settings is
    the onboarding; the banner choice is its first fieldset, sent with
    registration). No choice yet -> no announcement (the default). A member
    who has already been paid-announced was charged, so the free trigger
    no longer applies to them. Deduped: at most one free announcement per
    member, ever.
    """
    if choice not in CHOICES:
        return None
    if await _find_typed(db, user_id, "paid"):
        return None
    return await _record_announcement(db, user_id, choice, display_name_raw,
                                      fallback_handle, paid=False)


async def note_payment_collected(db, user_id: str) -> dict | None:
    """PAID trigger: a first payment has actually been COLLECTED.

    Fires only when a banner opt-in is on file (the member's stored
    ``welcome_choice``); announces every paying member, including members
    already free-announced — the paid announcement is a distinct second
    announcement. Deduped: at most one paid announcement per member, ever
    (calling this twice changes nothing).

    Called by the billing webhook (app/billing.py) once a verified Stripe
    checkout confirms the paid subscription. Never call it speculatively.
    """
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return None
    choice = user.get("welcome_choice")
    if choice not in CHOICES:
        return None  # no opt-in on file: silence, however much they paid
    # The display name on file was already sanitized when it was stored.
    return await _record_announcement(db, user_id, choice,
                                      user.get("welcome_display_name"),
                                      user.get("handle"), paid=True)


async def set_welcome_choice(db, user: dict, choice: str | None,
                             display_name_raw=None) -> dict | None:
    """Apply a member's later choice change immediately.

    ``choice=None`` means "no announcement": any live announcements are
    removed. ``optout`` strips the name from the live announcements in
    place, at once. A member with no announcement yet who now chooses is
    completing the banner part of onboarding while uncharged (no payment
    flow exists in this app), so that first announcement is the free one.
    Returns a live announcement doc, or None.
    """
    user_id = user["_id"]
    if choice not in CHOICES:
        await db[COLLECTION].delete_many({"user_id": user_id})
        return None
    kind, name = _kind_and_name(choice, display_name_raw, user.get("handle"))
    cursor = db[COLLECTION].find({"user_id": user_id})
    existing = await cursor.to_list(length=MAX_STORED)
    if existing:
        for doc in existing:
            update = {"kind": kind}
            if name:
                update["display_name"] = name
            await db[COLLECTION].update_one({"_id": doc["_id"]}, {"$set": update})
            if not name:
                await db[COLLECTION].update_one({"_id": doc["_id"]}, {"$unset": {"display_name": ""}})
        return await db[COLLECTION].find_one({"_id": existing[0]["_id"]})
    return await note_onboarding_completed(db, user_id, choice, display_name_raw, user.get("handle"))


async def feed(db) -> list[dict]:
    cursor = db[COLLECTION].find({}).sort("created_at", -1).limit(MAX_FEED)
    docs = await cursor.to_list(length=MAX_FEED)
    return [public_announcement(d) for d in docs]
