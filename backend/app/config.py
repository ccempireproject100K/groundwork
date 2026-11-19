"""Settings. The product name lives in ONE place: APP_NAME (env GW_APP_NAME).

Rename the product by changing DEFAULT_APP_NAME here (backend) and
frontend/src/brand.js (frontend). Nothing else hard-codes the name.
"""
import os
from dataclasses import dataclass

DEFAULT_APP_NAME = "Groundwork"  # finalists: Groundwork / Commissary Club ("Refresh" is taken)


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    app_name: str = DEFAULT_APP_NAME
    mongo_url: str = "mongodb://localhost:27017"
    db_name: str = "groundwork"
    token_ttl_minutes: int = 12 * 60
    timezone: str = "America/Chicago"
    # Key-encryption key for the document vault envelope (base64, 32 bytes).
    # Dev/test only default is empty -> vault endpoints refuse to run.
    vault_kek_b64: str = ""
    crisis_line: str = "988"
    emergency_line: str = "911"
    # Federated sign-in (app/federated.py; owner order 2026-11-10).
    # Env-gated PER PROVIDER: empty id/secret -> provider invisible,
    # endpoints 503. Apple is READY ONLY (paid Apple Developer Program
    # gate, $99/yr) and is never enabled this wave.
    frontend_origin: str = "http://localhost:5173"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_redirect_uri: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = ""
    apple_client_id: str = ""
    apple_client_secret: str = ""
    apple_redirect_uri: str = ""
    # Billing (app/billing.py). Both Stripe values empty -> the billing
    # endpoints answer 503 and nothing is ever granted. public_url is the
    # site's own origin: checkout return URLs are built from it, never from
    # anything the client sends.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    public_url: str = ""
    # "production" (the default) never derives an OAuth redirect URI from the
    # request's Host header; set GW_ENV=development for local work.
    environment: str = "production"
    # Sign-in rate limiting (app/ratelimit.py). A limit of 0 turns it off.
    login_max_attempts_ip: int = 30
    login_max_attempts_handle: int = 10
    login_window_seconds: int = 900
    login_lockout_seconds: int = 900
    trusted_proxies: int = 0



def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        raise RuntimeError(f"{name} must be a whole number") from None


def load_settings() -> Settings:
    secret = os.environ.get("GW_JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("GW_JWT_SECRET must be set to at least 32 characters")
    return Settings(
        jwt_secret=secret,
        app_name=os.environ.get("GW_APP_NAME", DEFAULT_APP_NAME),
        mongo_url=os.environ.get("GW_MONGO_URL", "mongodb://localhost:27017"),
        db_name=os.environ.get("GW_DB_NAME", "groundwork"),
        vault_kek_b64=os.environ.get("GW_VAULT_KEK", ""),
        frontend_origin=os.environ.get("GW_FRONTEND_ORIGIN", "http://localhost:5173"),
        google_client_id=os.environ.get("GW_GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.environ.get("GW_GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.environ.get("GW_GOOGLE_REDIRECT_URI", ""),
        facebook_app_id=os.environ.get("GW_FACEBOOK_APP_ID", ""),
        facebook_app_secret=os.environ.get("GW_FACEBOOK_APP_SECRET", ""),
        facebook_redirect_uri=os.environ.get("GW_FACEBOOK_REDIRECT_URI", ""),
        microsoft_client_id=os.environ.get("GW_MICROSOFT_CLIENT_ID", ""),
        microsoft_client_secret=os.environ.get("GW_MICROSOFT_CLIENT_SECRET", ""),
        microsoft_redirect_uri=os.environ.get("GW_MICROSOFT_REDIRECT_URI", ""),
        linkedin_client_id=os.environ.get("GW_LINKEDIN_CLIENT_ID", ""),
        linkedin_client_secret=os.environ.get("GW_LINKEDIN_CLIENT_SECRET", ""),
        linkedin_redirect_uri=os.environ.get("GW_LINKEDIN_REDIRECT_URI", ""),
        apple_client_id=os.environ.get("GW_APPLE_CLIENT_ID", ""),
        apple_client_secret=os.environ.get("GW_APPLE_CLIENT_SECRET", ""),
        apple_redirect_uri=os.environ.get("GW_APPLE_REDIRECT_URI", ""),
        stripe_secret_key=os.environ.get("GW_STRIPE_SECRET_KEY", "").strip(),
        stripe_webhook_secret=os.environ.get("GW_STRIPE_WEBHOOK_SECRET", "").strip(),
        public_url=os.environ.get("GW_PUBLIC_URL", "").strip(),
        environment=os.environ.get("GW_ENV", "production").strip().lower() or "production",
        login_max_attempts_ip=_int_env("GW_LOGIN_MAX_ATTEMPTS_IP", 30),
        login_max_attempts_handle=_int_env("GW_LOGIN_MAX_ATTEMPTS_HANDLE", 10),
        login_window_seconds=max(1, _int_env("GW_LOGIN_WINDOW_SECONDS", 900)),
        login_lockout_seconds=max(1, _int_env("GW_LOGIN_LOCKOUT_SECONDS", 900)),
        trusted_proxies=_int_env("GW_TRUSTED_PROXIES", 0),
    )
