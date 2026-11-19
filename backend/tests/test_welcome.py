"""Welcome banner acceptance tests (owner spec, 2026-11-02; final trigger
rules, 2026-11-03).

Covers: the FREE trigger (opt-in + onboarding completed = a successful
registration carrying a choice, while uncharged) producing FREE-tagged
entries; the PAID trigger (opt-in + first payment actually collected, via
welcome.note_payment_collected — uncalled in the app because no payment
provider/event exists yet) producing a DISTINCT, untagged-as-free second
announcement marked paid; dedupe per announcement type (max one free +
one paid per member); named / anonymous / opt-out / not-chosen cases;
privacy and display-name safety; real events only (no announcement on
login, none fabricated); capped history; later opt-outs honored
immediately.
"""
import asyncio

from app import welcome


def register(client, handle, **extra):
    body = {"handle": handle, "password": "long-enough-password", **extra}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def feed(client):
    r = client.get("/api/welcome/feed")
    assert r.status_code == 200
    return r.json()["announcements"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_choice_means_no_announcement_by_default(client):
    register(client, "quietjoiner")
    assert feed(client) == []


def test_named_choice_announces_the_chosen_display_name(client):
    # Registration carrying a named choice = onboarding completed while
    # uncharged -> the FREE announcement, tagged as such.
    register(client, "somehandle", welcome_choice="named", welcome_display_name="Young Builder")
    items = feed(client)
    assert items == [{"kind": "named", "display_name": "Young Builder", "free": True,
                      "created_at": items[0]["created_at"]}]


def test_named_without_display_name_falls_back_to_the_public_handle(client):
    register(client, "handlefan", welcome_choice="named")
    items = feed(client)
    assert items[0]["kind"] == "named"
    assert items[0]["display_name"] == "handlefan"
    assert items[0]["free"] is True


def test_anonymous_choice_announces_no_name(client):
    register(client, "shymember", welcome_choice="anonymous", welcome_display_name="Should Not Show")
    items = feed(client)
    assert items[0]["kind"] == "anonymous"
    assert items[0]["free"] is True
    assert "display_name" not in items[0]


def test_optout_choice_is_generic_and_never_named(client):
    register(client, "privateperson", welcome_choice="optout", welcome_display_name="Never Show Me")
    items = feed(client)
    assert items[0]["kind"] == "generic"
    assert items[0]["free"] is True
    assert "display_name" not in items[0]
    assert "privateperson" not in str(items)


def test_registration_is_the_free_trigger_even_when_a_paid_tier_is_selected(client):
    # Selecting a tier at registration collects NO payment (no payment
    # provider exists in this app), so every registration announcement is
    # the FREE one, whatever tier name was picked. An untagged/paid entry
    # is impossible without welcome.note_payment_collected().
    register(client, "freemember", tier="free", welcome_choice="named", welcome_display_name="Free One")
    register(client, "paidmember", tier="paid", welcome_choice="named", welcome_display_name="Paid One")
    items = feed(client)
    assert {i["display_name"] for i in items} == {"Free One", "Paid One"}
    for item in items:
        # The free tag is the ONLY type label; no tier / price / payment
        # fields ride along.
        assert set(item) == {"kind", "display_name", "created_at", "free"}
        assert item["free"] is True


def test_feed_never_exposes_contact_or_identity_fields(client):
    register(client, "contactful", phone="555-123-4567", welcome_choice="named",
             welcome_display_name="Safe Name")
    raw = str(feed(client))
    assert "555" not in raw and "contactful" not in raw
    item = feed(client)[0]
    assert "user_id" not in item and "_id" not in item and "phone" not in item and "email" not in item


def test_login_creates_no_announcement(client):
    r = register(client, "loginonly", welcome_choice="none" if False else None)
    before = len(feed(client))
    resp = client.post("/api/auth/login", json={"handle": "loginonly", "password": "long-enough-password"})
    assert resp.status_code == 200
    assert len(feed(client)) == before == 0
    assert r["user"]["handle"] == "loginonly"


def test_unsafe_display_names_fall_back_to_anonymous(client):
    # Email-like, phone-like, URL-like, and markup names must never publish.
    register(client, "u1x", welcome_choice="named", welcome_display_name="me@example.com")
    register(client, "u2x", welcome_choice="named", welcome_display_name="call 555 123 4567")
    register(client, "u3x", welcome_choice="named", welcome_display_name="visit www.example.com")
    register(client, "u4x", welcome_choice="named", welcome_display_name="<script>alert(1)</script>")
    items = feed(client)
    assert all(i["kind"] == "anonymous" for i in items), items
    raw = str(items)
    assert "@" not in raw and "555" not in raw and "<script>" not in raw and "www" not in raw


def test_display_name_is_capped_and_cleaned():
    name = welcome.sanitize_display_name("  A   very\tlong  display name that goes on and on  ")
    assert name is not None and len(name) <= welcome.MAX_NAME_LENGTH
    assert "  " not in name and "\t" not in name
    assert welcome.sanitize_display_name("") is None
    assert welcome.sanitize_display_name(None) is None


def test_invalid_welcome_choice_is_rejected(client):
    r = client.post("/api/auth/register", json={"handle": "badchoice", "password": "long-enough-password",
                                                "welcome_choice": "shout-my-email"})
    assert r.status_code == 422
    assert feed(client) == []


def test_later_optout_strips_the_name_immediately(client):
    r = register(client, "changer", welcome_choice="named", welcome_display_name="Now You See Me")
    assert feed(client)[0]["display_name"] == "Now You See Me"
    resp = client.put("/api/welcome/choice", json={"choice": "optout"}, headers=auth(r["token"]))
    assert resp.status_code == 200
    items = feed(client)
    assert items[0]["kind"] == "generic"
    assert "Now You See Me" not in str(items) and "display_name" not in items[0]


def test_later_none_removes_the_announcement(client):
    r = register(client, "remover", welcome_choice="anonymous")
    assert len(feed(client)) == 1
    resp = client.put("/api/welcome/choice", json={"choice": "none"}, headers=auth(r["token"]))
    assert resp.status_code == 200
    assert feed(client) == []


def test_late_choice_after_default_creates_one_announcement(client):
    r = register(client, "latepicker")
    assert feed(client) == []
    resp = client.put("/api/welcome/choice", json={"choice": "named", "display_name": "Late Bloomer"},
                      headers=auth(r["token"]))
    assert resp.status_code == 200
    items = feed(client)
    assert len(items) == 1 and items[0]["display_name"] == "Late Bloomer"
    assert items[0]["free"] is True  # completed onboarding uncharged -> free entry


def test_choice_changes_dedupe_to_one_announcement_per_member(client):
    r = register(client, "flipper", welcome_choice="anonymous")
    for choice in ("named", "anonymous", "optout", "named"):
        body = {"choice": choice, "display_name": "Flipper"}
        resp = client.put("/api/welcome/choice", json=body, headers=auth(r["token"]))
        assert resp.status_code == 200
    items = feed(client)
    assert len(items) == 1
    assert items[0]["kind"] == "named"


def test_feed_is_capped_and_storage_is_pruned(client, db):
    async def seed():
        for i in range(welcome.MAX_STORED + 15):
            await welcome.note_onboarding_completed(db, f"fixture-user-{i}", "anonymous")
    asyncio.run(seed())
    stored = None

    async def count():
        return await db[welcome.COLLECTION].count_documents({})
    stored = asyncio.run(count())
    assert stored == welcome.MAX_STORED
    assert len(feed(client)) == welcome.MAX_FEED


def test_feed_sends_a_cache_header(client):
    r = client.get("/api/welcome/feed")
    assert r.headers.get("cache-control") == f"public, max-age={welcome.CACHE_MAX_AGE_SECONDS}"


def test_choice_endpoint_requires_login(client):
    assert client.put("/api/welcome/choice", json={"choice": "anonymous"}).status_code == 401
    assert client.get("/api/welcome/me").status_code == 401


def test_fixture_names_are_only_in_tests(client):
    # The live feed starts empty: nothing is fabricated for the banner.
    assert feed(client) == []


# --- PAID trigger: welcome.note_payment_collected() -----------------------
# The hook is UNCALLED in the app (no payment provider / payment-collected
# event exists yet); these tests exercise it directly as a unit, the way a
# future real payment flow will call it when a first payment is collected.

def seed_user_with_optin(db, user_id, handle, choice, display_name=None):
    async def seed():
        await db.users.insert_one({"_id": user_id, "handle": handle,
                                   "welcome_choice": choice,
                                   "welcome_display_name": welcome.sanitize_display_name(display_name)})
    asyncio.run(seed())


def call_payment_hook(db, user_id):
    return asyncio.run(welcome.note_payment_collected(db, user_id))


def user_id_for(db, handle):
    async def find():
        user = await db.users.find_one({"handle": handle})
        return user["_id"]
    return asyncio.run(find())


def test_payment_hook_announces_unannounced_optin_member_paid_without_free_tag(client, db):
    # Direct-paid: opt-in on file, never announced, first payment collected
    # -> exactly one announcement, marked paid, NO free tag.
    seed_user_with_optin(db, "fixture-pay-1", "directpayer", "named", "Fixture Payer")
    doc = call_payment_hook(db, "fixture-pay-1")
    assert doc is not None
    items = feed(client)
    assert items == [{"kind": "named", "display_name": "Fixture Payer", "paid": True,
                      "created_at": items[0]["created_at"]}]
    assert "free" not in items[0]


def test_payment_hook_after_free_announcement_adds_a_second_paid_announcement(client, db):
    register(client, "converter", welcome_choice="named", welcome_display_name="Converting Member")
    assert len(feed(client)) == 1 and feed(client)[0]["free"] is True
    doc = call_payment_hook(db, user_id_for(db, "converter"))
    assert doc is not None
    items = feed(client)
    assert len(items) == 2
    paid_items = [i for i in items if i.get("paid") is True]
    free_items = [i for i in items if i.get("free") is True]
    assert len(paid_items) == 1 and len(free_items) == 1
    # The paid (conversion) announcement is the newer one and carries no
    # free tag; the original free announcement is untouched.
    assert items[0] == paid_items[0]
    assert paid_items[0]["display_name"] == "Converting Member"
    assert "free" not in paid_items[0] and "paid" not in free_items[0]


def test_payment_hook_called_twice_still_one_paid_announcement(client, db):
    seed_user_with_optin(db, "fixture-pay-2", "twicepayer", "named", "Fixture Twice")
    call_payment_hook(db, "fixture-pay-2")
    call_payment_hook(db, "fixture-pay-2")
    items = feed(client)
    assert len(items) == 1 and items[0]["paid"] is True


def test_payment_hook_without_optin_on_file_announces_nothing(client, db):
    seed_user_with_optin(db, "fixture-pay-3", "silentpayer", None)
    assert call_payment_hook(db, "fixture-pay-3") is None
    assert feed(client) == []
    # And for a member who does not exist at all.
    assert call_payment_hook(db, "fixture-pay-nobody") is None
    assert feed(client) == []


def test_payment_hook_for_anonymous_member_is_paid_and_nameless(client, db):
    seed_user_with_optin(db, "fixture-pay-4", "shypayer", "anonymous", "Should Not Show")
    doc = call_payment_hook(db, "fixture-pay-4")
    assert doc is not None
    items = feed(client)
    assert items[0]["kind"] == "anonymous" and items[0]["paid"] is True
    assert "display_name" not in items[0] and "free" not in items[0]
    assert "Should Not Show" not in str(items) and "shypayer" not in str(items)
