"""Federated (social) sign-in — ONE provider-agnostic layer.

Providers: google, facebook, microsoft, linkedin and apple (READY
ONLY this wave: plumbing + callback shape exist, never enabled, no
button — activation waits on the owner's paid Apple Developer
Program membership, $99/yr).

Discipline (owner order 2026-11-10):
- Additive: handle/password auth is untouched.
- Env-gated PER PROVIDER (GW_<PROVIDER>_CLIENT_ID / _SECRET): a
  provider with no credentials is invisible and its endpoints 503.
- ID tokens verified SERVER-SIDE against provider JWKS (signature,
  issuer, audience == our client id, expiry). Facebook deviation: no
  OIDC id_token — the access token is validated via Graph
  debug_token (valid + issued for OUR app) and /me; a Facebook-
  returned email counts as verified. Microsoft deviation: no
  email_verified claim exists, so a Microsoft email is NEVER trusted:
  Microsoft accounts link by the stable (provider, sub) identity only
  and no Microsoft email is stored or matched.
- OIDC nonce: a random nonce is stored with the sign-in state and the
  id_token's nonce claim must match it.
- Sign-in state (state, nonce, redirect URI, expiry) lives in the
  database, so any worker can finish a sign-in another one started.
- Redirect URI: from configuration (GW_<PROVIDER>_REDIRECT_URI, else
  GW_PUBLIC_URL). The request Host header is used only when
  GW_ENV is a development value.
- Linking by VERIFIED email or the durable (provider, sub) identity
  stored on the user record (``identities`` — inside the users
  document, so the one-tap wipe in app/wipe.py covers it). Apple
  links by provider ID only, never by email (private relay).
- Groundwork's ordinary registration is handle + password with NO
  email field, so a federated signup derives a unique handle from
  the email prefix and stores the verified email on the record;
  role/tier defaults match password registration exactly
  (member / free, plan selection is not a grant).
- Tests monkeypatch ``verify_provider_token`` / ``exchange_code``
  with a fake provider — no live calls in the suite.
"""
from __future__ import annotations

import hashlib
import secrets as _secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWKClient

# provider id -> (label, kind, Settings id attr, secret attr, redirect attr, urls...)
PROVIDERS: dict[str, dict] = {
    "google": {
        "label": "Google", "kind": "oidc",
        "id_attr": "google_client_id", "secret_attr": "google_client_secret",
        "redirect_attr": "google_redirect_uri",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "jwks_url": "https://www.googleapis.com/oauth2/v3/certs",
        "issuers": ("https://accounts.google.com", "accounts.google.com"),
        "scopes": "openid email profile", "require_email_verified": True,
    },
    "facebook": {
        "label": "Facebook", "kind": "facebook",
        "id_attr": "facebook_app_id", "secret_attr": "facebook_app_secret",
        "redirect_attr": "facebook_redirect_uri",
        "authorize_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scopes": "email,public_profile", "require_email_verified": False,
    },
    "microsoft": {
        "label": "Microsoft", "kind": "oidc",
        "id_attr": "microsoft_client_id", "secret_attr": "microsoft_client_secret",
        "redirect_attr": "microsoft_redirect_uri",
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "jwks_url": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        "issuers": None, "scopes": "openid email profile",
        "require_email_verified": False,
    },
    "linkedin": {
        "label": "LinkedIn", "kind": "oidc",
        "id_attr": "linkedin_client_id", "secret_attr": "linkedin_client_secret",
        "redirect_attr": "linkedin_redirect_uri",
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "jwks_url": "https://www.linkedin.com/oauth/openid/jwks",
        "issuers": ("https://www.linkedin.com",),
        "scopes": "openid profile email", "require_email_verified": True,
    },
    "apple": {
        "label": "Apple", "kind": "apple",
        "id_attr": "apple_client_id", "secret_attr": "apple_client_secret",
        "redirect_attr": "apple_redirect_uri",
        "authorize_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "jwks_url": "https://appleid.apple.com/auth/keys",
        "issuers": ("https://appleid.apple.com",),
        "scopes": "name email", "require_email_verified": False,
    },
}

APPLE_GATE = ("Sign in with Apple requires a paid Apple Developer "
              "Program membership ($99/yr) — not activated this wave.")


def client_id(settings, provider: str) -> str:
    return getattr(settings, PROVIDERS[provider]["id_attr"], "")


def client_secret(settings, provider: str) -> str:
    return getattr(settings, PROVIDERS[provider]["secret_attr"], "")


def provider_enabled(settings, provider: str) -> bool:
    if provider not in PROVIDERS or provider == "apple":
        return False  # apple: money gate — plumbing only this wave
    return bool(client_id(settings, provider)
                and client_secret(settings, provider))


def enabled_providers(settings) -> list[dict]:
    return [{"id": pid, "label": m["label"]}
            for pid, m in PROVIDERS.items()
            if provider_enabled(settings, pid)]


class RedirectNotConfigured(ValueError):
    """No redirect URI is configured for the provider (production)."""


DEV_ENVIRONMENTS = ("development", "dev", "local", "test")


def redirect_uri(settings, provider: str, request_base: str = "") -> str:
    """The OAuth redirect URI. Configuration wins; the request's own base URL
    (derived from the Host header) is only a development convenience."""
    explicit = getattr(settings, PROVIDERS[provider]["redirect_attr"], "")
    if explicit:
        return explicit
    public = (getattr(settings, "public_url", "") or "").strip().rstrip("/")
    if public:
        return f"{public}/api/auth/{provider}/callback"
    if (getattr(settings, "environment", "production") or "").lower() in DEV_ENVIRONMENTS:
        base = (request_base or settings.frontend_origin).rstrip("/")
        return f"{base}/api/auth/{provider}/callback"
    raise RedirectNotConfigured(f"{provider} redirect URI is not configured")


def build_authorize_url(settings, provider: str, state: str,
                        redirect: str, nonce: str | None = None) -> str:
    meta = PROVIDERS[provider]
    params = {
        "client_id": client_id(settings, provider),
        "redirect_uri": redirect,
        "response_type": "code", "scope": meta["scopes"], "state": state,
    }
    if meta["kind"] == "oidc" and nonce:
        params["nonce"] = nonce
    return meta["authorize_url"] + "?" + urllib.parse.urlencode(params)


def exchange_code(settings, provider: str, code: str, redirect: str) -> str:
    """Code -> token exchange (secret stays server-side). Returns the
    id_token (OIDC) or access token (Facebook). Tests monkeypatch."""
    import httpx

    meta = PROVIDERS[provider]
    resp = httpx.post(meta["token_url"], data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect,
        "client_id": client_id(settings, provider),
        "client_secret": client_secret(settings, provider),
    }, timeout=15)
    resp.raise_for_status()
    token = resp.json().get("id_token") or resp.json().get("access_token")
    if not token:
        raise ValueError("provider returned no token")
    return token


_jwk_clients: dict[str, PyJWKClient] = {}


def verify_oidc_id_token(settings, provider: str, id_token: str) -> dict:
    meta = PROVIDERS[provider]
    jwks = _jwk_clients.setdefault(provider, PyJWKClient(meta["jwks_url"]))
    key = jwks.get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(id_token, key, algorithms=["RS256"],
                        audience=client_id(settings, provider),
                        options={"require": ["exp", "iss", "sub"]})
    iss = claims.get("iss", "")
    if meta["issuers"] is not None and iss not in meta["issuers"]:
        raise ValueError(f"unexpected issuer {iss!r}")
    if meta["issuers"] is None and not (
            iss.startswith("https://login.microsoftonline.com/")
            or iss.startswith("https://sts.windows.net/")):
        raise ValueError(f"unexpected issuer {iss!r}")
    return claims


def verify_facebook_token(settings, access_token: str) -> dict:
    import httpx

    app_id = client_id(settings, "facebook")
    app_secret = client_secret(settings, "facebook")
    dbg = httpx.get("https://graph.facebook.com/v19.0/debug_token",
                    params={"input_token": access_token,
                            "access_token": f"{app_id}|{app_secret}"},
                    timeout=15)
    dbg.raise_for_status()
    data = dbg.json().get("data", {})
    if not data.get("is_valid") or str(data.get("app_id")) != str(app_id):
        raise ValueError("facebook token not valid for this app")
    me = httpx.get("https://graph.facebook.com/v19.0/me",
                   params={"fields": "id,name,email",
                           "access_token": access_token}, timeout=15)
    me.raise_for_status()
    profile = me.json()
    if not profile.get("id"):
        raise ValueError("facebook profile missing id")
    return {"sub": str(profile["id"]),
            "email": (profile.get("email") or "").lower() or None,
            "email_verified": bool(profile.get("email")),
            "name": profile.get("name") or ""}


_MS_CONSUMERS_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"


def verify_provider_token(settings, provider: str, token: str) -> dict:
    """THE verification entry point (tests monkeypatch this). Returns
    {sub, email, email_verified, name, nonce}; raises ValueError on failure."""
    meta = PROVIDERS[provider]
    if meta["kind"] == "facebook":
        return verify_facebook_token(settings, token)
    claims = verify_oidc_id_token(settings, provider, token)
    email = claims.get("email")
    out = {"sub": str(claims["sub"]),
           "email": email.lower() if email else None,
           "email_verified": bool(claims.get("email_verified")),
           "name": claims.get("name") or "",
           "nonce": claims.get("nonce")}
    if meta["require_email_verified"] and out["email"] \
            and not out["email_verified"]:
        raise ValueError("provider email is not verified")
    if provider == "microsoft":
        # Microsoft asserts no verified-email claim: never trust the address.
        out["email"] = None
        out["email_verified"] = False
    return out


def nonce_matches(provider: str, expected: str | None, claims: dict) -> bool:
    """OIDC providers must echo the nonce stored with the sign-in state."""
    if PROVIDERS[provider]["kind"] != "oidc":
        return True
    got = claims.get("nonce")
    return bool(expected) and isinstance(got, str) and _secrets.compare_digest(got, expected)


# OAuth state: stored in the database (collection oauth_states) so it works
# with several workers. Holds NO member data (random values, a provider name
# and a redirect URI), so it stays out of the wipe collections. The state
# value itself is never stored, only its SHA-256. Entries expire after
# STATE_TTL_SECONDS (a TTL index also removes them) and are single use.
STATE_TTL_SECONDS = 600
STATE_COLLECTION = "oauth_states"


def _state_id(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def new_state(db, provider: str, redirect: str, now: datetime | None = None) -> tuple[str, str]:
    """Create a sign-in attempt. Returns (state, nonce)."""
    now = now or datetime.now(timezone.utc)
    state = _secrets.token_urlsafe(32)
    nonce = _secrets.token_urlsafe(16)
    await db[STATE_COLLECTION].insert_one({
        "_id": _state_id(state), "provider": provider, "nonce": nonce,
        "redirect_uri": redirect, "created_at": now,
        "expires_at": now + timedelta(seconds=STATE_TTL_SECONDS)})
    return state, nonce


async def consume_state(db, state: str, provider: str, now: datetime | None = None) -> dict | None:
    """Single use: returns the stored attempt (nonce, redirect_uri) or None."""
    if not state:
        return None
    now = now or datetime.now(timezone.utc)
    doc = await db[STATE_COLLECTION].find_one_and_delete({"_id": _state_id(state)})
    if not doc or doc.get("provider") != provider:
        return None
    if _aware(doc.get("expires_at")) <= now:
        return None
    return doc
