"""Shared test helpers.

Registration always creates a free member or family account. Tests that need
a paid tier or the admin role set that state directly in the database (the way
a payment confirmation or an operator would) and then sign in again so the
token carries the stored role.
"""
import asyncio

PASSWORD = "password123"


def set_user_state(client, handle: str, **fields) -> None:
    """Write fields (for example tier="paid", role="admin") straight to the users collection."""
    db = client.app.state.db
    res = asyncio.run(db.users.update_one({"handle": handle}, {"$set": fields}))
    assert res.matched_count == 1, handle


def register_user(client, handle, tier="free", role="member", password=PASSWORD, **extra):
    """Register through the API, then apply tier/role through the database.

    Returns the same {"token", "user"} shape the API returns, taken from a
    fresh login when any state was changed so the token matches the stored role.
    """
    body = {"handle": handle, "password": password, **extra}
    if role in ("member", "family"):
        body["role"] = role
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    state = {}
    if tier != "free":
        state["tier"] = tier
    if role not in ("member", "family"):
        state["role"] = role
    if state:
        set_user_state(client, handle, **state)
        r = client.post("/api/auth/login", json={"handle": handle, "password": password})
        assert r.status_code == 200, r.text
        out = r.json()
    return out
