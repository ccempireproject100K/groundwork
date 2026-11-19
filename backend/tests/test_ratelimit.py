"""Sign-in rate limiting: per address and per handle, shared through the database."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.config import Settings
from app.main import create_app
from helpers import register_user


def make_client(db, **kw):
    base = dict(jwt_secret="t" * 40)
    base.update(kw)
    return TestClient(create_app(Settings(**base), db=db))


def login(c, handle, password="wrong-password", headers=None):
    return c.post("/api/auth/login", json={"handle": handle, "password": password}, headers=headers or {})


def test_handle_locks_after_the_limit_and_blocks_even_the_right_password(db):
    with make_client(db, login_max_attempts_handle=3, login_max_attempts_ip=0) as c:
        register_user(c, "victim")
        assert [login(c, "victim").status_code for _ in range(3)] == [401, 401, 401]
        r = login(c, "victim", "password123")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) > 0
        # Another handle is not affected by this handle's lock.
        register_user(c, "bystander")
        assert login(c, "bystander", "password123").status_code == 200


def test_ip_limit_applies_across_handles(db):
    with make_client(db, login_max_attempts_ip=4, login_max_attempts_handle=0) as c:
        for i in range(4):
            assert login(c, f"nobody{i}").status_code == 401
        assert login(c, "anyone", "x").status_code == 429


def test_different_addresses_are_counted_separately_behind_a_trusted_proxy(db):
    with make_client(db, login_max_attempts_ip=2, login_max_attempts_handle=0, trusted_proxies=1) as c:
        a = {"X-Forwarded-For": "203.0.113.5"}
        b = {"X-Forwarded-For": "203.0.113.6"}
        assert login(c, "x", headers=a).status_code == 401
        assert login(c, "x", headers=a).status_code == 401
        assert login(c, "x", headers=a).status_code == 429
        assert login(c, "x", headers=b).status_code == 401


def test_forwarded_header_is_ignored_without_trusted_proxies(db):
    with make_client(db, login_max_attempts_ip=2, login_max_attempts_handle=0) as c:
        for i in range(2):
            assert login(c, "x", headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code == 401
        assert login(c, "x", headers={"X-Forwarded-For": "198.51.100.99"}).status_code == 429


def test_successful_login_clears_the_handle_counter(db):
    with make_client(db, login_max_attempts_handle=3, login_max_attempts_ip=0) as c:
        register_user(c, "forgetful")
        login(c, "forgetful"); login(c, "forgetful")
        assert login(c, "forgetful", "password123").status_code == 200
        login(c, "forgetful"); login(c, "forgetful")
        assert login(c, "forgetful", "password123").status_code == 200


def test_limits_of_zero_disable_the_check(db):
    with make_client(db, login_max_attempts_handle=0, login_max_attempts_ip=0) as c:
        for _ in range(15):
            assert login(c, "ghost").status_code == 401
        assert asyncio.run(db.login_attempts.count_documents({})) == 0


def test_lock_expires_and_window_resets(db):
    s = Settings(jwt_secret="t" * 40, login_max_attempts_handle=2, login_max_attempts_ip=0,
                 login_window_seconds=60, login_lockout_seconds=60)
    pairs = ratelimit.keys_for(s, "1.2.3.4", "Alice")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def run():
        await ratelimit.record_failure(db, s, pairs, now=t0)
        await ratelimit.record_failure(db, s, pairs, now=t0 + timedelta(seconds=1))
        assert await ratelimit.locked_for(db, pairs, now=t0 + timedelta(seconds=2)) > 0
        assert await ratelimit.locked_for(db, pairs, now=t0 + timedelta(seconds=120)) == 0
        # A failure after the window starts a fresh count of one, not a lock.
        await ratelimit.record_failure(db, s, pairs, now=t0 + timedelta(seconds=200))
        assert await ratelimit.locked_for(db, pairs, now=t0 + timedelta(seconds=201)) == 0

    asyncio.run(run())


def test_handle_key_is_case_insensitive_and_not_stored_raw(db):
    with make_client(db, login_max_attempts_handle=2, login_max_attempts_ip=0) as c:
        login(c, "MixedCase"); login(c, "mixedcase")
        assert login(c, "MIXEDCASE").status_code == 429
        ids = [d["_id"] for d in asyncio.run(db.login_attempts.find({}).to_list(10))]
        assert ids and all("mixedcase" not in i.lower() for i in ids)


@pytest.mark.parametrize("name,value", [("GW_LOGIN_MAX_ATTEMPTS_IP", "7"), ("GW_LOGIN_WINDOW_SECONDS", "30")])
def test_knobs_come_from_the_environment(monkeypatch, name, value):
    from app.config import load_settings
    monkeypatch.setenv("GW_JWT_SECRET", "s" * 40)
    monkeypatch.setenv(name, value)
    s = load_settings()
    assert int(value) in (s.login_max_attempts_ip, s.login_window_seconds)


def test_bad_knob_value_is_refused(monkeypatch):
    from app.config import load_settings
    monkeypatch.setenv("GW_JWT_SECRET", "s" * 40)
    monkeypatch.setenv("GW_LOGIN_MAX_ATTEMPTS_IP", "lots")
    with pytest.raises(RuntimeError):
        load_settings()
