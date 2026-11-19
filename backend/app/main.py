from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, load_settings
from .routers import (billing, community, family, journey, learning, matching, meta, platform, reentry, safety,
                      support, venue, welcome, wellbeing, work)

ROUTERS = (meta, safety, reentry, work, support, community, journey, wellbeing, learning, matching, venue,
           family, platform, welcome, billing)


async def ensure_indexes(db) -> None:
    """Indexes for the hot lookups (login, federated sign-in, AI usage meter).
    Non-unique and best-effort: a failure here must never stop the app starting."""
    wanted = (
        ("users", [("handle", 1)]),
        ("users", [("email", 1)]),
        ("users", [("identities.provider", 1), ("identities.sub", 1)]),
        ("ai_usage", [("user_id", 1), ("created_at", 1)]),
    )
    for coll, keys in wanted:
        try:
            await db[coll].create_index(keys)
        except Exception:
            pass
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
