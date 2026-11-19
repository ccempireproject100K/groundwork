"""Federated sign-in tests — FAKE provider only, no live calls.
Token strings encode claims: fake:<email>:<sub>:<verified 0|1>."""
import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app import federated
from app.config import Settings
from app.main import create_app

PROVIDERS = ["google", "facebook", "microsoft", "linkedin"]
CREDS = {
    "google": {"google_client_id": "g-id", "google_client_secret": "g-secret"},
    "facebook": {"facebook_app_id": "f-id", "facebook_app_secret": "f-secret"},
    "microsoft": {"microsoft_client_id": "m-id", "microsoft_client_secret": "m-secret"},
    "linkedin": {"linkedin_client_id": "l-id", "linkedin_client_secret": "l-secret"},
    "apple": {"apple_client_id": "a-id", "apple_client_secret": "a-secret"},
}


def fake_verify(settings, provider, token):
    if token == "bad":
        raise ValueError("bad token")
    _, email, sub, verified = token.split(":")
    return {"sub": sub, "email": email,
            "email_verified": verified == "1", "name": "Fed User"}


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    monkeypatch.setattr(federated, "verify_provider_token", fake_verify)
    monkeypatch.setattr(federated, "exchange_code",
                        lambda settings, provider, code, base="": code)


def make_client(**creds):
    settings = Settings(jwt_secret="x" * 40, **creds)
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


@pytest.mark.parametrize("provider", PROVIDERS)
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
    settings = Settings(jwt_secret="x" * 40, **CREDS[provider], **CREDS[other])
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


def test_callback_requires_matching_browser_cookie():
    client, db = make_client(**CREDS["google"])
    state = federated.new_state("google")  # state issued, but never to this browser
    cb = client.get("/api/auth/google/callback",
                    params={"code": tok("x@example.com", "g-x"), "state": state},
                    follow_redirects=False)
    assert cb.status_code == 400


def test_state_expires(monkeypatch):
    state = federated.new_state("google")
    late = federated._STATES[state][1] + 1
    monkeypatch.setattr(federated.time, "monotonic", lambda: late)
    assert federated.consume_state(state, "google") is False
