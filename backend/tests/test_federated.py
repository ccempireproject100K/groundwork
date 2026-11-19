"""Federated sign-in tests — FAKE provider only, no live calls.
Token strings encode claims: fake:<email>:<sub>:<verified 0|1>."""
import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app import federated
from app.config import Settings
from app.main import create_app

REAL_VERIFY = federated.verify_provider_token  # the autouse fixture replaces the module attribute

PROVIDERS = ["google", "facebook", "microsoft", "linkedin"]
EMAIL_LINKING = ["google", "facebook", "linkedin"]  # Microsoft never links by email
PUBLIC = "https://gw.example.test"
CREDS = {
    "google": {"google_client_id": "g-id", "google_client_secret": "g-secret"},
    "facebook": {"facebook_app_id": "f-id", "facebook_app_secret": "f-secret"},
    "microsoft": {"microsoft_client_id": "m-id", "microsoft_client_secret": "m-secret"},
    "linkedin": {"linkedin_client_id": "l-id", "linkedin_client_secret": "l-secret"},
    "apple": {"apple_client_id": "a-id", "apple_client_secret": "a-secret"},
}


FAKE_NONCE = {"value": None}  # what the fake provider echoes as the id_token nonce


def fake_verify(settings, provider, token):
    if token == "bad":
        raise ValueError("bad token")
    _, email, sub, verified = token.split(":")
    return {"sub": sub, "email": email,
            "email_verified": verified == "1", "name": "Fed User",
            "nonce": FAKE_NONCE["value"]}


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    monkeypatch.setattr(federated, "verify_provider_token", fake_verify)
    monkeypatch.setattr(federated, "exchange_code",
                        lambda settings, provider, code, redirect="": code)
    FAKE_NONCE["value"] = None


def make_client(**creds):
    settings = Settings(jwt_secret="x" * 40, public_url=PUBLIC, **creds)
    db = AsyncMongoMockClient()["gw_fed_test"]
    return TestClient(create_app(settings, db=db)), db


def tok(email, sub, verified=1):
    return f"fake:{email}:{sub}:{verified}"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_signup_creates_member_free(provider):
    client, db = make_client(**CREDS[provider])
    r = client.post(f"/api/auth/{provider}/token",
                    json={"token": tok("new@example.com", f"{provider}-1")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"]
    assert body["user"]["role"] == "member"
    assert body["user"]["tier"] == "free"
    assert "email" not in body["user"]  # private field stays private
    assert "identities" not in body["user"]
    me = client.get("/api/auth/me",
                    headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200


@pytest.mark.parametrize("provider", PROVIDERS)
def test_returning_login_same_account(provider):
    client, db = make_client(**CREDS[provider])
    payload = {"token": tok("back@example.com", f"{provider}-2")}
    first = client.post(f"/api/auth/{provider}/token", json=payload)
    second = client.post(f"/api/auth/{provider}/token", json=payload)
    assert first.json()["user"]["handle"] == second.json()["user"]["handle"]


@pytest.mark.parametrize("provider", EMAIL_LINKING)
def test_link_by_verified_email(provider):
    client, db = make_client(**CREDS[provider])
    # federated account first (it is the one carrying an email on file)
    first = client.post(f"/api/auth/{provider}/token",
                        json={"token": tok("link@example.com", f"{provider}-a")})
    handle = first.json()["user"]["handle"]
    # a second provider with the same verified email links, no duplicate
    other = "google" if provider != "google" else "facebook"
    client2, _ = make_client(**CREDS[provider], **CREDS[other])
    # same db is required for linking; rebuild against the same db:
    settings = Settings(jwt_secret="x" * 40, public_url=PUBLIC, **CREDS[provider], **CREDS[other])
    client2 = TestClient(create_app(settings, db=db))
    second = client2.post(f"/api/auth/{other}/token",
                          json={"token": tok("link@example.com", f"{other}-b")})
    assert second.status_code == 200, second.text
    assert second.json()["user"]["handle"] == handle


@pytest.mark.parametrize("provider", ["google", "linkedin"])
def test_unverified_email_refused(provider):
    client, db = make_client(**CREDS[provider])
    r = client.post(f"/api/auth/{provider}/token",
                    json={"token": tok("unv@example.com", f"{provider}-5", 0)})
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("provider", PROVIDERS)
def test_bad_token_refused(provider):
    client, db = make_client(**CREDS[provider])
    r = client.post(f"/api/auth/{provider}/token", json={"token": "bad"})
    assert r.status_code == 401


@pytest.mark.parametrize("provider", PROVIDERS)
def test_provider_off_invisible_and_503(provider):
    client, db = make_client()
    assert client.get("/api/auth/providers").json()["providers"] == []
    r = client.post(f"/api/auth/{provider}/token",
                    json={"token": tok("x@example.com", "s1")})
    assert r.status_code == 503
    assert client.get(f"/api/auth/{provider}/start").status_code == 503


def test_apple_never_enabled():
    client, db = make_client(**CREDS["apple"])
    listed = client.get("/api/auth/providers").json()["providers"]
    assert all(p["id"] != "apple" for p in listed)
    r = client.get("/api/auth/apple/start")
    assert r.status_code == 503
    assert "Apple Developer" in r.json()["detail"]


def test_start_and_callback_flow():
    client, db = make_client(**CREDS["google"])
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert start.status_code == 307
    assert start.headers["location"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth")
    state = start.headers["location"].split("state=")[1].split("&")[0]
    FAKE_NONCE["value"] = _query(start.headers["location"])["nonce"]
    cb = client.get("/api/auth/google/callback",
                    params={"code": tok("cb@example.com", "g-cb"),
                            "state": state},
                    follow_redirects=False)
    assert cb.status_code == 307, cb.text
    assert "#token=" in cb.headers["location"]


def test_password_regression(client):
    r = client.post("/api/auth/register",
                    json={"handle": "plainuser", "password": "password123"})
    assert r.status_code == 201
    ok = client.post("/api/auth/login",
                     json={"handle": "plainuser", "password": "password123"})
    assert ok.status_code == 200
    bad = client.post("/api/auth/login",
                      json={"handle": "plainuser", "password": "nope-nope"})
    assert bad.status_code == 401


def _query(url):
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}


def test_callback_requires_matching_browser_cookie():
    client, db = make_client(**CREDS["google"])
    state, nonce = asyncio.run(federated.new_state(db, "google", PUBLIC + "/cb"))  # never issued to this browser
    FAKE_NONCE["value"] = nonce
    cb = client.get("/api/auth/google/callback",
                    params={"code": tok("x@example.com", "g-x"), "state": state},
                    follow_redirects=False)
    assert cb.status_code == 400


def test_state_expires():
    client, db = make_client(**CREDS["google"])
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state, _ = asyncio.run(federated.new_state(db, "google", PUBLIC + "/cb", now=t0))
    late = t0 + timedelta(seconds=federated.STATE_TTL_SECONDS + 1)
    assert asyncio.run(federated.consume_state(db, state, "google", now=late)) is None


def test_state_is_single_use_and_provider_bound():
    client, db = make_client(**CREDS["google"])
    state, nonce = asyncio.run(federated.new_state(db, "google", PUBLIC + "/cb"))
    assert asyncio.run(federated.consume_state(db, state, "facebook")) is None  # wrong provider (and now spent)
    state, nonce = asyncio.run(federated.new_state(db, "google", PUBLIC + "/cb"))
    doc = asyncio.run(federated.consume_state(db, state, "google"))
    assert doc["nonce"] == nonce and doc["redirect_uri"] == PUBLIC + "/cb"
    assert asyncio.run(federated.consume_state(db, state, "google")) is None
    assert asyncio.run(federated.consume_state(db, "", "google")) is None


def test_state_is_shared_between_workers_and_never_stored_raw():
    """Two app instances on one database: one starts, the other finishes."""
    client_a, db = make_client(**CREDS["google"])
    client_b = TestClient(create_app(Settings(jwt_secret="x" * 40, public_url=PUBLIC, **CREDS["google"]), db=db))
    start = client_a.get("/api/auth/google/start", follow_redirects=False)
    state = _query(start.headers["location"])["state"]
    FAKE_NONCE["value"] = _query(start.headers["location"])["nonce"]
    stored = asyncio.run(db.oauth_states.find({}).to_list(10))
    assert len(stored) == 1 and state not in stored[0]["_id"]
    client_b.cookies.set("gw_oauth_state", state)
    cb = client_b.get("/api/auth/google/callback", params={"code": tok("w@example.com", "g-w"), "state": state},
                      follow_redirects=False)
    assert cb.status_code == 307, cb.text


def test_callback_rejects_missing_or_wrong_nonce():
    client, db = make_client(**CREDS["google"])
    for echoed in (None, "not-the-nonce"):
        start = client.get("/api/auth/google/start", follow_redirects=False)
        state = _query(start.headers["location"])["state"]
        FAKE_NONCE["value"] = echoed
        cb = client.get("/api/auth/google/callback", params={"code": tok("n@example.com", "g-n"), "state": state},
                        follow_redirects=False)
        assert cb.status_code == 401, echoed
    assert asyncio.run(db.users.count_documents({})) == 0


def test_authorize_url_carries_the_stored_nonce_for_oidc_only():
    client, db = make_client(**CREDS["google"], **CREDS["facebook"])
    g = client.get("/api/auth/google/start", follow_redirects=False)
    stored = asyncio.run(db.oauth_states.find({}).to_list(10))
    assert _query(g.headers["location"])["nonce"] == stored[0]["nonce"]
    f = client.get("/api/auth/facebook/start", follow_redirects=False)
    assert "nonce" not in _query(f.headers["location"])


def test_facebook_callback_needs_no_nonce():
    client, db = make_client(**CREDS["facebook"])
    start = client.get("/api/auth/facebook/start", follow_redirects=False)
    state = _query(start.headers["location"])["state"]
    cb = client.get("/api/auth/facebook/callback", params={"code": tok("fb@example.com", "fb-1"), "state": state},
                    follow_redirects=False)
    assert cb.status_code == 307, cb.text


def test_nonce_matches_unit():
    assert federated.nonce_matches("google", "abc", {"nonce": "abc"})
    assert not federated.nonce_matches("google", "abc", {"nonce": "abd"})
    assert not federated.nonce_matches("google", "abc", {})
    assert not federated.nonce_matches("google", None, {"nonce": None})
    assert federated.nonce_matches("facebook", None, {})


# ---- redirect URI: configuration, never the Host header, in production ----

def test_redirect_uri_comes_from_public_url_not_host_header():
    client, db = make_client(**CREDS["google"])
    start = client.get("/api/auth/google/start", headers={"Host": "evil.example"}, follow_redirects=False)
    assert _query(start.headers["location"])["redirect_uri"] == PUBLIC + "/api/auth/google/callback"
    stored = asyncio.run(db.oauth_states.find({}).to_list(10))
    assert stored[0]["redirect_uri"] == PUBLIC + "/api/auth/google/callback"


def test_explicit_redirect_uri_wins():
    client, db = make_client(google_redirect_uri="https://login.example.test/cb", **CREDS["google"])
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert _query(start.headers["location"])["redirect_uri"] == "https://login.example.test/cb"


def test_production_without_any_redirect_config_refuses():
    settings = Settings(jwt_secret="x" * 40, **CREDS["google"])
    client = TestClient(create_app(settings, db=AsyncMongoMockClient()["gw_fed_prod"]))
    assert client.get("/api/auth/google/start", headers={"Host": "evil.example"}, follow_redirects=False).status_code == 503


def test_development_may_use_the_request_base():
    settings = Settings(jwt_secret="x" * 40, environment="development", **CREDS["google"])
    client = TestClient(create_app(settings, db=AsyncMongoMockClient()["gw_fed_dev"]))
    start = client.get("/api/auth/google/start", follow_redirects=False)
    assert _query(start.headers["location"])["redirect_uri"] == "http://testserver/api/auth/google/callback"


def test_environment_defaults_to_production(monkeypatch):
    from app.config import load_settings
    monkeypatch.setenv("GW_JWT_SECRET", "s" * 40)
    monkeypatch.delenv("GW_ENV", raising=False)
    assert load_settings().environment == "production"
    monkeypatch.setenv("GW_ENV", "Development")
    assert load_settings().environment == "development"


# ---- Microsoft: stable subject only, an email claim is never trusted ----

def test_microsoft_links_by_subject_only_and_stores_no_email():
    client, db = make_client(**CREDS["microsoft"])
    a = client.post("/api/auth/microsoft/token", json={"token": tok("who@example.com", "ms-sub-1")})
    b = client.post("/api/auth/microsoft/token", json={"token": tok("changed@example.com", "ms-sub-1")})
    assert a.status_code == b.status_code == 200
    assert a.json()["user"]["handle"] == b.json()["user"]["handle"]
    users = asyncio.run(db.users.find({}).to_list(10))
    assert len(users) == 1 and "email" not in users[0]
    assert users[0]["identities"] == [{"provider": "microsoft", "sub": "ms-sub-1"}]


def test_microsoft_email_never_takes_over_an_existing_account(db):
    settings = Settings(jwt_secret="x" * 40, public_url=PUBLIC, **CREDS["google"], **CREDS["microsoft"])
    client = TestClient(create_app(settings, db=db))
    g = client.post("/api/auth/google/token", json={"token": tok("victim@example.com", "g-victim")})
    # An attacker's Microsoft account claims the victim's address, marked verified.
    m = client.post("/api/auth/microsoft/token", json={"token": tok("victim@example.com", "ms-attacker", 1)})
    assert m.status_code == 200
    assert m.json()["user"]["handle"] != g.json()["user"]["handle"]
    victim = asyncio.run(db.users.find_one({"email": "victim@example.com"}))
    assert victim["identities"] == [{"provider": "google", "sub": "g-victim"}]


def test_microsoft_token_verification_drops_the_email(monkeypatch):
    claims = {"sub": "s1", "email": "Boss@Example.com", "email_verified": True, "tid": "tenant", "xms_edov": "true",
              "preferred_username": "boss@example.com", "name": "Boss", "nonce": "n"}
    monkeypatch.setattr(federated, "verify_oidc_id_token", lambda settings, provider, token: dict(claims))
    out = REAL_VERIFY(Settings(jwt_secret="x" * 40), "microsoft", "tok")
    assert out["sub"] == "s1" and out["email"] is None and out["email_verified"] is False
    assert out["nonce"] == "n"
    # Other OIDC providers still report their verified email.
    out = REAL_VERIFY(Settings(jwt_secret="x" * 40), "google", "tok")
    assert out["email"] == "boss@example.com" and out["email_verified"] is True




def test_signup_retries_when_the_derived_handle_is_taken_concurrently(monkeypatch):
    from app.main import ensure_indexes
    from app.routers import meta
    client, db = make_client(**CREDS["google"])
    asyncio.run(ensure_indexes(db))
    asyncio.run(db.users.insert_one({"_id": "existing", "handle": "racehandle", "role": "member", "tier": "free"}))
    picks = iter(["racehandle", "racehandle2"])

    async def racing_unique_handle(db_, email):
        return next(picks)

    monkeypatch.setattr(meta, "_unique_handle", racing_unique_handle)
    r = client.post("/api/auth/google/token", json={"token": tok("race@example.com", "g-race")})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["handle"] == "racehandle2"
    assert asyncio.run(db.users.count_documents({"handle": "racehandle"})) == 1
