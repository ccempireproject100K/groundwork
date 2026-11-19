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
