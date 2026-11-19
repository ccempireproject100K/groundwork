"""Health, feature registry, plan table, and auth (member/family/admin)."""
import uuid
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from .. import federated, ratelimit, registry, safety, security, tiers, welcome
from ..deps import get_current_user

router = APIRouter(prefix="/api", tags=["meta"])

class RegisterIn(BaseModel):
    handle: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    role: str = "member"
    phone: str | None = None
    # Welcome banner choice: onboarding's FIRST question. None = not chosen
    # yet, which defaults to NO public announcement. See app/welcome.py.
    welcome_choice: str | None = None
    welcome_display_name: str | None = Field(default=None, max_length=80)

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
    # Self-service sign-up only creates member or family accounts, always on
    # the free plan. Any tier supplied by the client is ignored: a paid plan
    # is granted only by a confirmed payment (app/billing.py).
    if body.role not in security.REGISTRABLE_ROLES:
        raise HTTPException(422, "invalid role")
    if body.welcome_choice is not None and body.welcome_choice not in welcome.CHOICES:
        raise HTTPException(422, "invalid welcome choice")
    db = request.app.state.db
    if await db.users.find_one({"handle": body.handle}):
        raise HTTPException(409, "handle taken")
    uid = uuid.uuid4().hex
    doc = {"_id": uid, "handle": body.handle, "password_hash": security.hash_password(body.password), "role": body.role, "tier": "free", "phone": body.phone,
           "welcome_choice": body.welcome_choice,
           "welcome_display_name": welcome.sanitize_display_name(body.welcome_display_name)}
    await db.users.insert_one(doc)
    # FREE welcome trigger (owner's final rules, 2026-11-03): account creation
    # is the onboarding and the banner choice arrives with registration, so a
    # registration carrying a choice, while uncharged, earns the FREE-tagged
    # announcement. Selecting a paid tier is NOT a payment: the paid
    # announcement can only come from welcome.note_payment_collected(), which
    # the billing webhook calls once a payment is confirmed. Never on login.
    await welcome.note_onboarding_completed(db, uid, body.welcome_choice,
                                            body.welcome_display_name, body.handle)
    token = security.make_token(request.app.state.settings.jwt_secret, uid, body.role, request.app.state.settings.token_ttl_minutes)
    return {"token": token, "user": safety.public_member(doc)}

@router.post("/auth/login")
async def login(body: LoginIn, request: Request):
    db = request.app.state.db
    settings = request.app.state.settings
    pairs = ratelimit.keys_for(settings, ratelimit.client_ip(request, settings.trusted_proxies), body.handle)
    wait = await ratelimit.locked_for(db, pairs)
    if wait:
        raise HTTPException(429, "too many sign-in attempts, try again later", headers={"Retry-After": str(wait)})
    user = await db.users.find_one({"handle": body.handle})
    if not user or not security.verify_password(user.get("password_hash"), body.password):
        await ratelimit.record_failure(db, settings, pairs)
        raise HTTPException(401, "invalid credentials")
    await ratelimit.clear_handle(db, settings, body.handle)
    token = security.make_token(settings.jwt_secret, user["_id"], user.get("role", "member"), settings.token_ttl_minutes)
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
import secrets as _secrets

_STATE_COOKIE = "gw_oauth_state"
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
    user = await db.users.find_one(
        {"identities": {"$elemMatch": {"provider": provider, "sub": sub}}})
    if user is not None:
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
    resp = RedirectResponse(url, status_code=307)
    # Bind the sign-in attempt to this browser: the callback must present it.
    resp.set_cookie(_STATE_COOKIE, state, max_age=federated.STATE_TTL_SECONDS,
                    httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", path="/api/auth")
    return resp


@router.get("/auth/{provider}/callback")
async def federated_callback(provider: str, request: Request,
                             code: str = "", state: str = ""):
    _require_provider(request, provider)
    bound = request.cookies.get(_STATE_COOKIE, "")
    if not federated.consume_state(state, provider) or not _secrets.compare_digest(bound, state):
        raise HTTPException(400, "invalid or expired sign-in state")
    settings = request.app.state.settings
    try:
        token = await run_in_threadpool(federated.exchange_code, settings, provider, code,
                                        str(request.base_url))
        claims = await run_in_threadpool(federated.verify_provider_token, settings, provider, token)
    except Exception:
        raise HTTPException(401, "provider sign-in could not be verified")
    user = await _federated_resolve(request, provider, claims)
    session = _federated_session(request, user)
    resp = RedirectResponse(
        f"{settings.frontend_origin.rstrip('/')}/settings#token={session['token']}",
        status_code=307)
    resp.delete_cookie(_STATE_COOKIE, path="/api/auth")
    return resp


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
        claims = await run_in_threadpool(federated.verify_provider_token, settings, provider, body.token)
    except Exception:
        raise HTTPException(401, "provider token could not be verified")
    user = await _federated_resolve(request, provider, claims)
    return _federated_session(request, user)
