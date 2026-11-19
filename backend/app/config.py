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
    )
