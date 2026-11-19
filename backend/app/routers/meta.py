"""Health, feature registry, plan table, and auth (member/family/admin)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .. import federated, registry, safety, security, tiers
from ..deps import get_current_user

router = APIRouter(prefix="/api", tags=["meta"])

class RegisterIn(BaseModel):
    handle: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    role: str = "member"
    phone: str | None = None
    tier: str = "free"

class LoginIn(BaseModel):
    handle: str
    password: str

@router.get("/health")
async def health(request: Request):
    return {"ok": True, "app": request.app.state.settings.app_name}

@router.get("/features")
async def features():
    return {"count": len(registry.FEATURES), "features": registry.all_features()}

@router.get("/features/{feature_id}")
async def feature(feature_id: str):
    if feature_id not in registry.BY_ID:
        raise HTTPException(404, "unknown feature")
    return registry.get(feature_id).to_dict()

@router.get("/plans")
async def plans():
    return tiers.plan_table()

@router.post("/auth/register", status_code=201)
async def register(body: RegisterIn, request: Request):
    if body.role not in security.ROLES:
        raise HTTPException(422, "invalid role")
    if body.tier not in ("free", "paid"):
        raise HTTPException(422, "invalid tier")
    db = request.app.state.db
    if await db.users.find_one({"handle": body.handle}):
        raise HTTPException(409, "handle taken")
    uid = uuid.uuid4().hex
    doc = {"_id": uid, "handle": body.handle, "password_hash": security.hash_password(body.password), "role": body.role, "tier": body.tier, "phone": body.phone}
    await db.users.insert_one(doc)
    token = security.make_token(request.app.state.settings.jwt_secret, uid, body.role, request.app.state.settings.token_ttl_minutes)
    return {"token": token, "user": safety.public_member(doc)}

@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    db = request.app.state.db
    user = await db.users.find_one({"handle": body.handle})
    if not user or not security.verify_password(user.get("password_hash"), body.password):
        raise HTTPException(401, "invalid credentials")
    token = security.make_token(request.app.state.settings.jwt_secret, user["_id"], user.get("role", "member"), request.app.state.settings.token_ttl_minutes)
    return {"token": token, "user": safety.public_member(user)}

@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return safety.public_member(user)


# ---------------------------------------------------------------------
# Federated sign-in (owner order 2026-11-10): ONE provider-agnostic
# layer (app/federated.py) — google / facebook / microsoft / linkedin,
# apple READY ONLY (never enabled this wave; $99/yr developer gate).
# Handle/password above is untouched.
# ---------------------------------------------------------------------
import re as _re
from fastapi.responses import RedirectResponse


class FederatedTokenIn(BaseModel):
    token: str


def _require_provider(request: Request, provider: str):
    if provider not in federated.PROVIDERS:
        raise HTTPException(404, "unknown provider")
    if provider == "apple":
        raise HTTPException(503, federated.APPLE_GATE)
    if not federated.provider_enabled(request.app.state.settings, provider):
        raise HTTPException(503, f"{provider} sign-in is not configured")


async def _unique_handle(db, email: str) -> str:
    base = _re.sub(r"[^a-z0-9_]", "_", email.split("@")[0].lower()).strip("_")
    if len(base) < 2:
        base = "member"
    handle, n = base, 2
    while await db.users.find_one({"handle": handle}):
        handle = f"{base}{n}"
        n += 1
    return handle


async def _federated_resolve(request: Request, provider: str, claims: dict):
    db = request.app.state.db
    sub = claims["sub"]
    # 1) durable identity match
    async for user in db.users.find({}):
        if any(i.get("provider") == provider and i.get("sub") == sub
               for i in (user.get("identities") or [])):
            return user
    email = claims.get("email")
    # 2) link by VERIFIED email (never for apple — private relay)
    if provider != "apple" and email and claims.get("email_verified"):
        user = await db.users.find_one({"email": email})
        if user is not None:
            identities = list(user.get("identities") or [])
            identities.append({"provider": provider, "sub": sub})
            providers = list(user.get("auth_providers") or ["password"])
            if provider not in providers:
                providers.append(provider)
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"identities": identities,
                          "auth_providers": providers}})
            user["identities"] = identities
            user["auth_providers"] = providers
            return user
    # 3) new account — ordinary registration defaults (member / free)
    if provider == "apple":
        if not email:
            raise HTTPException(422, "Apple did not return an email address")
    elif not email or not claims.get("email_verified"):
        raise HTTPException(401, "provider did not return a verified email address")
    uid = uuid.uuid4().hex
    doc = {"_id": uid, "handle": await _unique_handle(db, email),
           "password_hash": None, "role": "member", "tier": "free",
           "phone": None, "email": email,
           "identities": [{"provider": provider, "sub": sub}],
           "auth_providers": [provider]}
    await db.users.insert_one(doc)
    return doc


def _federated_session(request: Request, user: dict) -> dict:
    settings = request.app.state.settings
    token = security.make_token(settings.jwt_secret, user["_id"],
                                user["role"], settings.token_ttl_minutes)
    return {"token": token, "user": safety.public_member(user)}


@router.get("/auth/providers")
async def auth_providers(request: Request):
    """Configured providers only — unconfigured = invisible."""
    return {"providers": federated.enabled_providers(request.app.state.settings)}


@router.get("/auth/{provider}/start")
async def federated_start(provider: str, request: Request):
    _require_provider(request, provider)
    settings = request.app.state.settings
    state = federated.new_state(provider)
    url = federated.build_authorize_url(settings, provider, state,
                                        str(request.base_url))
    return RedirectResponse(url, status_code=307)


@router.get("/auth/{provider}/callback")
async def federated_callback(provider: str, request: Request,
                             code: str = "", state: str = ""):
    _require_provider(request, provider)
    if not federated.consume_state(state, provider):
        raise HTTPException(400, "invalid or expired sign-in state")
    settings = request.app.state.settings
    try:
        token = federated.exchange_code(settings, provider, code,
                                        str(request.base_url))
        claims = federated.verify_provider_token(settings, provider, token)
    except Exception:
        raise HTTPException(401, "provider sign-in could not be verified")
    user = await _federated_resolve(request, provider, claims)
    session = _federated_session(request, user)
    return RedirectResponse(
        f"{settings.frontend_origin.rstrip('/')}/settings#token={session['token']}",
        status_code=307)


@router.post("/auth/{provider}/callback")
async def federated_callback_post(provider: str, request: Request):
    """Apple's form_post callback shape lands here once Apple is
    activated. This wave Apple is gated off — see federated.APPLE_GATE."""
    _require_provider(request, provider)
    raise HTTPException(503, "not available")


@router.post("/auth/{provider}/token")
async def federated_token(provider: str, body: FederatedTokenIn,
                          request: Request):
    """Direct token sign-in (mobile / tests): verified server-side,
    answered with the ordinary session shape {token, user}."""
    _require_provider(request, provider)
    settings = request.app.state.settings
    try:
        claims = federated.verify_provider_token(settings, provider, body.token)
    except Exception:
        raise HTTPException(401, "provider token could not be verified")
    user = await _federated_resolve(request, provider, claims)
    return _federated_session(request, user)
