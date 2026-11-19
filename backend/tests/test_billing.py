"""Billing: Stripe Checkout creation and the signed webhook. No real Stripe calls."""
import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from app import billing, tiers
from app.config import Settings
from app.main import create_app
from helpers import register_user

WH_SECRET = "whsec_test_secret_value"
SK = "sk_test_fake_key_for_tests"
PUBLIC = "https://app.example.test"


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def sign(payload: bytes, secret=WH_SECRET, ts=None):
    ts = int(time.time()) if ts is None else ts
    mac = hmac.new(secret.encode(), str(ts).encode() + b"." + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def post_event(client, event: dict, *, secret=WH_SECRET, ts=None, header=None):
    raw = json.dumps(event).encode()
    sig = header if header is not None else sign(raw, secret, ts)
    return client.post("/api/billing/webhook", content=raw, headers={"Stripe-Signature": sig, "Content-Type": "application/json"})


def completed(uid, *, event_id="evt_1", amount=None, currency="usd", tier="paid", sub="sub_1", cust="cus_1",
              status="paid", mode="subscription", ref="same", meta_uid="same"):
    amount = tiers.PLANS["paid"]["price_cents"] if amount is None else amount
    return {"id": event_id, "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_test_1", "mode": mode, "payment_status": status, "amount_total": amount, "currency": currency,
        "subscription": sub, "customer": cust,
        "client_reference_id": uid if ref == "same" else ref,
        "metadata": {"user_id": uid if meta_uid == "same" else meta_uid, "tier": tier}}}}


def sub_event(kind, sub_id, status, uid=None, event_id="evt_s1"):
    obj = {"id": sub_id, "status": status, "metadata": {"user_id": uid} if uid else {}}
    return {"id": event_id, "type": kind, "data": {"object": obj}}


@pytest.fixture
def bsettings():
    return Settings(jwt_secret="t" * 40, stripe_secret_key=SK, stripe_webhook_secret=WH_SECRET, public_url=PUBLIC)


@pytest.fixture
def bclient(bsettings, db):
    with TestClient(create_app(bsettings, db=db)) as c:
        yield c


@pytest.fixture
def stripe_calls():
    """Swap the Stripe HTTP transport; collect the requests made."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"})

    billing.HTTP_TRANSPORT = httpx.MockTransport(handler)
    yield calls
    billing.HTTP_TRANSPORT = None


def tier_of(db, uid):
    return asyncio.run(db.users.find_one({"_id": uid}))["tier"]


def uid_of(db, handle):
    return asyncio.run(db.users.find_one({"handle": handle}))["_id"]


# ---------------- not configured: fail closed ----------------

def test_unconfigured_endpoints_answer_503_and_grant_nothing(client, db):
    u = register_user(client, "nocfg")
    assert client.post("/api/billing/checkout", headers=auth(u["token"])).status_code == 503
    uid = uid_of(db, "nocfg")
    ev = completed(uid)
    raw = json.dumps(ev).encode()
    r = client.post("/api/billing/webhook", content=raw, headers={"Stripe-Signature": sign(raw)})
    assert r.status_code == 503
    assert tier_of(db, uid) == "free"
    assert client.get("/api/billing/status", headers=auth(u["token"])).json()["configured"] is False


@pytest.mark.parametrize("missing", ["stripe_secret_key", "stripe_webhook_secret", "public_url"])
def test_any_missing_setting_refuses_checkout(db, missing):
    kw = dict(jwt_secret="t" * 40, stripe_secret_key=SK, stripe_webhook_secret=WH_SECRET, public_url=PUBLIC)
    kw[missing] = ""
    with TestClient(create_app(Settings(**kw), db=db)) as c:
        u = register_user(c, "partial")
        assert c.post("/api/billing/checkout", headers=auth(u["token"])).status_code == 503


def test_webhook_refuses_without_webhook_secret_even_if_signed(db):
    s = Settings(jwt_secret="t" * 40, stripe_secret_key=SK, stripe_webhook_secret="", public_url=PUBLIC)
    with TestClient(create_app(s, db=db)) as c:
        u = register_user(c, "nosecret")
        uid = uid_of(db, "nosecret")
        assert post_event(c, completed(uid), secret="").status_code == 503
        assert tier_of(db, uid) == "free"
        assert u["user"]["tier"] == "free"


# ---------------- checkout ----------------

def test_checkout_requires_login(bclient):
    assert bclient.post("/api/billing/checkout").status_code == 401
    assert bclient.get("/api/billing/status").status_code == 401


def test_checkout_builds_session_from_tiers_and_settings_only(bclient, db, stripe_calls):
    u = register_user(bclient, "buyer")
    uid = uid_of(db, "buyer")
    r = bclient.post("/api/billing/checkout", headers=auth(u["token"]),
                     json={"tier": "free", "amount": 1, "success_url": "https://evil.test/", "price": 1})
    assert r.status_code == 200
    assert r.json() == {"url": "https://checkout.stripe.com/c/pay/cs_test_1"}
    assert len(stripe_calls) == 1
    req = stripe_calls[0]
    assert str(req.url) == "https://api.stripe.com/v1/checkout/sessions"
    assert req.headers["authorization"] == f"Bearer {SK}"
    form = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
    assert form["mode"] == "subscription"
    assert form["line_items[0][price_data][unit_amount]"] == str(tiers.PLANS["paid"]["price_cents"]) == "399"
    assert form["line_items[0][price_data][currency]"] == "usd"
    assert form["line_items[0][price_data][recurring][interval]"] == "month"
    assert form["line_items[0][quantity]"] == "1"
    assert form["success_url"].startswith(PUBLIC + "/") and form["cancel_url"].startswith(PUBLIC + "/")
    assert "evil.test" not in req.content.decode()
    assert form["client_reference_id"] == uid
    assert form["metadata[user_id]"] == uid and form["metadata[tier]"] == "paid"
    assert form["subscription_data[metadata][user_id]"] == uid
    # Creating a session grants nothing.
    assert tier_of(db, uid) == "free"


def test_checkout_url_ignores_host_header(bclient, stripe_calls):
    u = register_user(bclient, "hostile")
    bclient.post("/api/billing/checkout", headers={**auth(u["token"]), "Host": "evil.test", "Origin": "https://evil.test"})
    assert "evil.test" not in stripe_calls[0].content.decode()


def test_checkout_provider_failure_is_502_and_hides_details(bclient):
    billing.HTTP_TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(402, json={"error": {"message": "secret detail"}}))
    try:
        u = register_user(bclient, "failer")
        r = bclient.post("/api/billing/checkout", headers=auth(u["token"]))
        assert r.status_code == 502 and "secret detail" not in r.text
    finally:
        billing.HTTP_TRANSPORT = None


def test_checkout_rejects_when_already_paid(bclient, stripe_calls):
    u = register_user(bclient, "already", tier="paid")
    assert bclient.post("/api/billing/checkout", headers=auth(u["token"])).status_code == 409
    assert stripe_calls == []


def test_status_reports_plan_from_tiers(bclient):
    u = register_user(bclient, "stat")
    body = bclient.get("/api/billing/status", headers=auth(u["token"])).json()
    assert body["configured"] is True and body["tier"] == "free"
    assert body["plan"] == {"tier": "paid", "name": tiers.PLANS["paid"]["name"], "price_cents": 399,
                            "currency": "usd", "interval": "month"}
    assert "stripe_customer_id" not in json.dumps(body)


# ---------------- webhook: signature ----------------

def test_valid_signed_checkout_grants_paid(bclient, db):
    u = register_user(bclient, "payer")
    uid = uid_of(db, "payer")
    r = post_event(bclient, completed(uid))
    assert r.status_code == 200 and r.json()["outcome"] == "granted"
    assert tier_of(db, uid) == "paid"
    doc = asyncio.run(db.users.find_one({"_id": uid}))
    assert doc["stripe_customer_id"] == "cus_1" and doc["stripe_subscription_id"] == "sub_1"
    me = bclient.get("/api/auth/me", headers=auth(u["token"])).json()
    assert me["tier"] == "paid"
    assert not {"stripe_customer_id", "stripe_subscription_id", "paid_at", "billing_status"} & set(me)
    assert bclient.get("/api/billing/status", headers=auth(u["token"])).json()["tier"] == "paid"


def test_bad_signature_is_rejected_and_grants_nothing(bclient, db):
    register_user(bclient, "forged")
    uid = uid_of(db, "forged")
    r = post_event(bclient, completed(uid), secret="whsec_wrong")
    assert r.status_code == 400
    assert tier_of(db, uid) == "free"
    assert asyncio.run(db.stripe_events.count_documents({})) == 0


def test_tampered_body_is_rejected(bclient, db):
    register_user(bclient, "tamper")
    uid = uid_of(db, "tamper")
    raw = json.dumps(completed(uid)).encode()
    sig = sign(raw)
    tampered = raw.replace(b"evt_1", b"evt_2")
    r = bclient.post("/api/billing/webhook", content=tampered, headers={"Stripe-Signature": sig})
    assert r.status_code == 400 and tier_of(db, uid) == "free"


@pytest.mark.parametrize("header", [None, "", "garbage", "t=abc,v1=00", "t=1", "v1=abcd"])
def test_missing_or_malformed_signature_header(bclient, db, header):
    register_user(bclient, "hdr")
    uid = uid_of(db, "hdr")
    raw = json.dumps(completed(uid)).encode()
    headers = {} if header is None else {"Stripe-Signature": header}
    r = bclient.post("/api/billing/webhook", content=raw, headers=headers)
    assert r.status_code == 400 and tier_of(db, uid) == "free"


def test_stale_timestamp_is_rejected(bclient, db):
    register_user(bclient, "stale")
    uid = uid_of(db, "stale")
    r = post_event(bclient, completed(uid), ts=int(time.time()) - 10 * 60)
    assert r.status_code == 400 and tier_of(db, uid) == "free"
    r = post_event(bclient, completed(uid), ts=int(time.time()) + 10 * 60)
    assert r.status_code == 400 and tier_of(db, uid) == "free"


def test_timestamp_inside_tolerance_is_accepted(bclient, db):
    register_user(bclient, "fresh")
    uid = uid_of(db, "fresh")
    assert post_event(bclient, completed(uid), ts=int(time.time()) - 240).status_code == 200
    assert tier_of(db, uid) == "paid"


def test_any_matching_v1_signature_is_enough(bclient, db):
    register_user(bclient, "rolling")
    uid = uid_of(db, "rolling")
    raw = json.dumps(completed(uid)).encode()
    good = sign(raw)
    header = f"{good},v1={'0' * 64}"
    assert bclient.post("/api/billing/webhook", content=raw, headers={"Stripe-Signature": header}).status_code == 200


# ---------------- webhook: idempotency and cross-checks ----------------

def test_replayed_event_id_is_processed_once(bclient, db):
    register_user(bclient, "replay")
    uid = uid_of(db, "replay")
    ev = completed(uid, event_id="evt_replay")
    assert post_event(bclient, ev).json()["outcome"] == "granted"
    # An operator downgrades the member; a replay must not re-grant.
    asyncio.run(db.users.update_one({"_id": uid}, {"$set": {"tier": "free"}}))
    r = post_event(bclient, ev)
    assert r.status_code == 200 and r.json()["duplicate"] is True
    assert tier_of(db, uid) == "free"
    assert asyncio.run(db.stripe_events.count_documents({"_id": "evt_replay"})) == 1


def test_wrong_amount_is_not_granted(bclient, db):
    register_user(bclient, "cheap")
    uid = uid_of(db, "cheap")
    for i, amount in enumerate((1, 398, 699, 0, None)):
        ev = completed(uid, event_id=f"evt_amt{i}")
        ev["data"]["object"]["amount_total"] = amount
        r = post_event(bclient, ev)
        assert r.status_code == 200 and r.json()["outcome"] == "rejected"
    assert tier_of(db, uid) == "free"


def test_wrong_currency_is_not_granted(bclient, db):
    register_user(bclient, "euro")
    uid = uid_of(db, "euro")
    r = post_event(bclient, completed(uid, currency="eur"))
    assert r.json()["outcome"] == "rejected" and tier_of(db, uid) == "free"


@pytest.mark.parametrize("kw", [
    {"tier": "top"}, {"status": "unpaid"}, {"mode": "payment"}, {"sub": None},
    {"meta_uid": "someone-else"}, {"meta_uid": None},
])
def test_other_checkout_mismatches_are_not_granted(bclient, db, kw):
    register_user(bclient, "mismatch")
    uid = uid_of(db, "mismatch")
    r = post_event(bclient, completed(uid, **kw))
    assert r.status_code == 200 and r.json()["outcome"] in ("rejected", "ignored")
    assert tier_of(db, uid) == "free"


def test_checkout_for_unknown_user_is_ignored(bclient, db):
    r = post_event(bclient, completed("no-such-user"))
    assert r.status_code == 200 and r.json()["outcome"] == "ignored"


def test_unknown_event_type_is_ignored(bclient, db):
    register_user(bclient, "unk")
    uid = uid_of(db, "unk")
    ev = {"id": "evt_unknown", "type": "invoice.created", "data": {"object": {"metadata": {"user_id": uid, "tier": "paid"}}}}
    r = post_event(bclient, ev)
    assert r.status_code == 200 and r.json()["outcome"] == "ignored"
    assert tier_of(db, uid) == "free"


def test_malformed_signed_payload_is_400(bclient):
    raw = b"not json"
    r = bclient.post("/api/billing/webhook", content=raw, headers={"Stripe-Signature": sign(raw)})
    assert r.status_code == 400
    raw = json.dumps({"type": "x"}).encode()
    assert bclient.post("/api/billing/webhook", content=raw, headers={"Stripe-Signature": sign(raw)}).status_code == 400


def test_failed_handler_releases_the_event_so_the_retry_runs(bclient, db, monkeypatch):
    register_user(bclient, "retry")
    uid = uid_of(db, "retry")
    real = billing.handle_event

    async def boom(db_, event):
        raise RuntimeError("db down")

    monkeypatch.setattr(billing, "handle_event", boom)
    assert post_event(bclient, completed(uid, event_id="evt_retry")).status_code == 500
    assert asyncio.run(db.stripe_events.count_documents({"_id": "evt_retry"})) == 0
    monkeypatch.setattr(billing, "handle_event", real)
    assert post_event(bclient, completed(uid, event_id="evt_retry")).json()["outcome"] == "granted"
    assert tier_of(db, uid) == "paid"


def test_payment_triggers_paid_welcome_announcement_when_opted_in(bclient, db):
    register_user(bclient, "cheer", welcome_choice="named", welcome_display_name="Cheer One")
    uid = uid_of(db, "cheer")
    post_event(bclient, completed(uid))
    docs = asyncio.run(db.welcome_announcements.find({"user_id": uid}).to_list(10))
    assert sum(1 for d in docs if d.get("paid") is True) == 1


def test_payment_without_welcome_opt_in_announces_nothing(bclient, db):
    register_user(bclient, "quiet")
    uid = uid_of(db, "quiet")
    post_event(bclient, completed(uid))
    assert asyncio.run(db.welcome_announcements.count_documents({"user_id": uid, "paid": True})) == 0


# ---------------- webhook: cancellation ----------------

def _paid_member(client, db, handle):
    register_user(client, handle)
    uid = uid_of(db, handle)
    post_event(client, completed(uid, event_id=f"evt_g_{handle}", sub=f"sub_{handle}"))
    assert tier_of(db, uid) == "paid"
    return uid


def test_subscription_deleted_returns_member_to_free(bclient, db):
    uid = _paid_member(bclient, db, "leaver")
    r = post_event(bclient, sub_event("customer.subscription.deleted", "sub_leaver", "canceled"))
    assert r.json()["outcome"] == "downgraded"
    assert tier_of(db, uid) == "free"


@pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete_expired"])
def test_subscription_updated_to_ended_status_downgrades(bclient, db, status):
    uid = _paid_member(bclient, db, "ender")
    post_event(bclient, sub_event("customer.subscription.updated", "sub_ender", status))
    assert tier_of(db, uid) == "free"


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_subscription_updated_to_live_status_changes_nothing(bclient, db, status):
    uid = _paid_member(bclient, db, "keeper")
    post_event(bclient, sub_event("customer.subscription.updated", "sub_keeper", status))
    assert tier_of(db, uid) == "paid"


def test_subscription_update_never_grants(bclient, db):
    register_user(bclient, "sneaky")
    uid = uid_of(db, "sneaky")
    post_event(bclient, sub_event("customer.subscription.updated", "sub_x", "active", uid=uid))
    assert tier_of(db, uid) == "free"


def test_old_subscription_cancel_does_not_downgrade_current_one(bclient, db):
    uid = _paid_member(bclient, db, "switcher")
    post_event(bclient, sub_event("customer.subscription.deleted", "sub_old", "canceled", uid=uid, event_id="evt_old"))
    assert tier_of(db, uid) == "paid"


# ---------------- unit: signature helper ----------------

def test_verify_signature_unit():
    raw = b'{"id":"evt"}'
    now = 1_700_000_000
    header = sign(raw, ts=now)
    billing.verify_signature(raw, header, WH_SECRET, now=now + 10)
    with pytest.raises(billing.SignatureError):
        billing.verify_signature(raw, header, WH_SECRET, now=now + 301)
    with pytest.raises(billing.SignatureError):
        billing.verify_signature(raw, header, "other", now=now)
    with pytest.raises(billing.SignatureError):
        billing.verify_signature(raw, header, "", now=now)


def test_flatten_encodes_nested_lists():
    assert billing.flatten({"a": {"b": [1, {"c": True}]}, "d": None}) == {"a[b][0]": "1", "a[b][1][c]": "true"}


def test_wipe_registers_billing_events():
    from app import wipe
    assert wipe.USER_COLLECTIONS["stripe_events"] == "user_id"
