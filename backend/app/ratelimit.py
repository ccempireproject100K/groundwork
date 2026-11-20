"""Sign-in rate limiting, per client address and per handle.

State lives in the database (collection login_attempts) so it holds across
several workers. Keys are keyed hashes of the address and the handle, never
the raw values. Only failed attempts count. After the limit is reached the
key is locked for GW_LOGIN_LOCKOUT_SECONDS and every attempt, correct password
or not, answers 429 until the lock ends. A limit of 0 turns that check off.

Knobs (Settings / environment):
  GW_LOGIN_MAX_ATTEMPTS_IP        failures per address per window (default 30)
  GW_LOGIN_MAX_ATTEMPTS_HANDLE    failures per handle per window  (default 10)
  GW_LOGIN_WINDOW_SECONDS         counting window                 (default 900)
  GW_LOGIN_LOCKOUT_SECONDS        lock length once the limit hits (default 900)
  GW_TRUSTED_PROXIES              reverse proxies in front of the app; the
                                  client address is then read from
                                  X-Forwarded-For (default 0, header ignored)
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

COLLECTION = "login_attempts"


def client_ip(request, trusted_proxies: int = 0) -> str:
    peer = request.client.host if request.client else "unknown"
    if trusted_proxies > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= trusted_proxies:
            return parts[-trusted_proxies]
    return peer


def _key(settings, kind: str, value: str) -> str:
    mac = hmac.new(settings.jwt_secret.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"{kind}:{mac[:40]}"


def keys_for(settings, ip: str, handle: str) -> list[tuple[str, int]]:
    """(key, limit) pairs that apply to one attempt, skipping disabled limits."""
    pairs = []
    if settings.login_max_attempts_ip > 0:
        pairs.append((_key(settings, "ip", ip), settings.login_max_attempts_ip))
    if settings.login_max_attempts_handle > 0:
        pairs.append((_key(settings, "handle", handle.strip().lower()), settings.login_max_attempts_handle))
    return pairs


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def locked_for(db, pairs, now: datetime | None = None) -> int:
    """Seconds left on the longest active lock, 0 when none."""
    now = now or datetime.now(timezone.utc)
    longest = 0
    for key, _limit in pairs:
        doc = await db[COLLECTION].find_one({"_id": key})
        until = _aware(doc.get("locked_until")) if doc else None
        if until and until > now:
            longest = max(longest, int((until - now).total_seconds()) + 1)
    return longest


async def record_failure(db, settings, pairs, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    window = timedelta(seconds=settings.login_window_seconds)
    for key, limit in pairs:
        coll = db[COLLECTION]
        doc = await coll.find_one({"_id": key})
        started = _aware(doc.get("window_start")) if doc else None
        if doc is None or started is None or now - started >= window:
            fresh = {"_id": key, "count": 1, "window_start": now, "locked_until": None,
                     "expires_at": now + window + timedelta(seconds=settings.login_lockout_seconds)}
            if doc is None:
                try:
                    await coll.insert_one(fresh)
                except DuplicateKeyError:
                    await coll.update_one({"_id": key}, {"$inc": {"count": 1}})
            else:
                await coll.replace_one({"_id": key}, fresh)
            count = 1
        else:
            await coll.update_one({"_id": key}, {"$inc": {"count": 1}})
            count = (await coll.find_one({"_id": key}))["count"]
        if count >= limit:
            await coll.update_one({"_id": key}, {"$set": {
                "locked_until": now + timedelta(seconds=settings.login_lockout_seconds),
                "expires_at": now + timedelta(seconds=settings.login_lockout_seconds + settings.login_window_seconds)}})


async def clear_handle(db, settings, handle: str) -> None:
    """A successful sign-in clears that handle's failures (not the address's)."""
    if settings.login_max_attempts_handle > 0:
        await db[COLLECTION].delete_one({"_id": _key(settings, "handle", handle.strip().lower())})
