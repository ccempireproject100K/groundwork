from app import registry


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"ok": True, "app": "Groundwork"}


def test_app_name_from_one_setting(db):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    with TestClient(create_app(Settings(jwt_secret="t" * 40, app_name="Commissary Club"), db=db)) as c:
        assert c.get("/api/health").json()["app"] == "Commissary Club"


def test_features_endpoint(client):
    body = client.get("/api/features").json()
    assert body["count"] == 51 and len(body["features"]) == 51


def test_every_feature_has_a_stub_route(client):
    for f in registry.FEATURES:
        if f.status == "working":
            continue
        r = client.get(f"/api/{f.group}/{f.id}")
        assert r.status_code == 501, f.id
        assert r.json()["feature"]["id"] == f.id


def test_plans(client):
    body = client.get("/api/plans").json()
    assert "crisis_button" in body["free"] and "document_vault" in body["paid"]


def test_ensure_indexes_runs_on_mock_db():
    import asyncio
    from mongomock_motor import AsyncMongoMockClient
    from app.main import ensure_indexes

    async def go():
        db = AsyncMongoMockClient()["gw_idx"]
        await ensure_indexes(db)
        return await db.users.index_information()

    info = asyncio.run(go())
    assert any("handle" in k for k in info)


def test_registration_always_creates_a_free_account(client):
    r = client.post("/api/auth/register", json={"handle": "reg_tier", "password": "password123", "tier": "paid"})
    assert r.status_code == 201
    assert r.json()["user"]["tier"] == "free"
    tok = r.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["tier"] == "free"


def test_registration_accepts_only_member_or_family_roles(client):
    for role in ("admin", "superuser", ""):
        r = client.post("/api/auth/register", json={"handle": f"reg_{role or 'blank'}", "password": "password123", "role": role})
        assert r.status_code == 422, role
    for role in ("member", "family"):
        r = client.post("/api/auth/register", json={"handle": f"ok_{role}", "password": "password123", "role": role})
        assert r.status_code == 201 and r.json()["user"]["role"] == role


# ---- handle uniqueness ----

def _unique_handle_index(db):
    import asyncio
    info = asyncio.run(db.users.index_information())
    return any(v.get("unique") and v["key"] == [("handle", 1)] for v in info.values())


def test_startup_creates_unique_handle_index():
    import asyncio
    from mongomock_motor import AsyncMongoMockClient
    from app.main import ensure_indexes
    db = AsyncMongoMockClient()["gw_uniq"]
    asyncio.run(ensure_indexes(db))
    assert _unique_handle_index(db)


def test_unique_index_replaces_an_older_plain_handle_index():
    import asyncio
    from mongomock_motor import AsyncMongoMockClient
    from app.main import ensure_unique_handle_index
    db = AsyncMongoMockClient()["gw_uniq2"]
    asyncio.run(db.users.create_index([("handle", 1)]))
    assert asyncio.run(ensure_unique_handle_index(db)) is True
    assert _unique_handle_index(db)


def test_existing_duplicates_are_logged_not_deleted_and_no_unique_index(caplog):
    import asyncio
    from mongomock_motor import AsyncMongoMockClient
    from app.main import ensure_unique_handle_index
    db = AsyncMongoMockClient()["gw_dupes"]
    asyncio.run(db.users.insert_many([{"_id": "a", "handle": "twin"}, {"_id": "b", "handle": "twin"}, {"_id": "c", "handle": "solo"}]))
    with caplog.at_level("ERROR", logger="groundwork.startup"):
        assert asyncio.run(ensure_unique_handle_index(db)) is False
    assert "twin" in caplog.text and "solo" not in caplog.text
    assert asyncio.run(db.users.count_documents({"handle": "twin"})) == 2
    assert not _unique_handle_index(db)


def test_registration_race_for_a_handle_answers_409(settings, db, monkeypatch):
    import asyncio
    from fastapi.testclient import TestClient
    from app.main import create_app, ensure_indexes
    asyncio.run(ensure_indexes(db))
    with TestClient(create_app(settings, db=db)) as c:
        assert c.post("/api/auth/register", json={"handle": "racer", "password": "password123"}).status_code == 201
        # Simulate the second request passing the pre-check before the first insert landed.
        real = db.users.find_one

        blinded = []

        async def blind(query, *a, **k):
            if query == {"handle": "racer"}:
                blinded.append(query)
                return None
            return await real(query, *a, **k)

        monkeypatch.setattr(type(db.users), "find_one", lambda self, q, *a, **k: blind(q, *a, **k), raising=False)
        r = c.post("/api/auth/register", json={"handle": "racer", "password": "password123"})
        assert r.status_code == 409
        assert blinded, "the pre-check was bypassed, so the 409 came from the unique index"
    assert asyncio.run(db.users.count_documents({"handle": "racer"})) == 1
