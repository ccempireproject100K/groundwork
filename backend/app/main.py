import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, load_settings
from .routers import (billing, community, family, journey, learning, matching, market, meta, platform, reentry, safety,
                      support, venue, welcome, wellbeing, work)

log = logging.getLogger("groundwork.startup")

ROUTERS = (meta, safety, reentry, work, support, community, journey, wellbeing, learning, matching, venue,
           family, platform, welcome, billing, market)


async def ensure_unique_handle_index(db) -> bool:
    """Make users.handle unique. Existing duplicates are never deleted or
    merged: they are logged, and the index falls back to a plain one until
    an operator resolves them. Returns True when the unique index exists."""
    try:
        dupes = await db.users.aggregate([
            {"$group": {"_id": "$handle", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gt": 1}}},
            {"$limit": 20},
        ]).to_list(20)
        if dupes:
            log.error("users.handle has %d duplicated value(s) (first %d: %s); unique index not created, "
                      "resolve them and restart", len(dupes), len(dupes), [d["_id"] for d in dupes])
            await db.users.create_index([("handle", 1)])
            return False
        try:
            await db.users.create_index([("handle", 1)], unique=True)
        except Exception:
            # An earlier plain handle index has the same key but not the
            # same options; replace it (safe: no duplicates were found).
            await db.users.drop_index("handle_1")
            await db.users.create_index([("handle", 1)], unique=True)
        return True
    except Exception:
        log.exception("could not create the unique handle index")
        return False


async def ensure_indexes(db) -> None:
    """Indexes for the hot lookups (login, federated sign-in, AI usage meter),
    plus the unique handle index. Best-effort: a failure here must never stop the app starting."""
    wanted = (
        ("users", [("email", 1)]),
        ("users", [("identities.provider", 1), ("identities.sub", 1)]),
        ("ai_usage", [("user_id", 1), ("created_at", 1)]),
    )
    for coll, keys in wanted:
        try:
            await db[coll].create_index(keys)
        except Exception:
            pass
    await ensure_unique_handle_index(db)
    for coll in ("login_attempts", "oauth_states"):  # these clean themselves up
        try:
            await db[coll].create_index("expires_at", expireAfterSeconds=0)
        except Exception:
            pass


def create_app(settings: Settings | None = None, db=None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.db is None:
            from motor.motor_asyncio import AsyncIOMotorClient

            app.state.db = AsyncIOMotorClient(settings.mongo_url, tz_aware=True)[settings.db_name]
            await ensure_indexes(app.state.db)
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    for module in ROUTERS:
        app.include_router(module.router)
    app.include_router(journey.public_router)
    return app
