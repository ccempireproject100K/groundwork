"""Market face (owner ruling 2026-11-01): stored choice, then edge country
(only when trusted), then the US default. Plan prices are never converted."""
from fastapi.testclient import TestClient

from app import marketface
from app.config import Settings
from app.main import create_app


def test_choice_wins_over_detection():
    assert marketface.resolve_market("ca", "GB") == ("ca", "choice")
    assert marketface.resolve_market(" AU ", None) == ("au", "choice")


def test_detection_beats_default_only_for_known_countries():
    assert marketface.resolve_market(None, "GB") == ("gb", "detected")
    assert marketface.resolve_market("", "uk") == ("gb", "detected")
    for unknown in ("ID", "XX", "T1", "USA", "1"):
        assert marketface.resolve_market(None, unknown) == ("us", "default")


def test_default_is_us_and_unknown_choice_is_ignored():
    assert marketface.resolve_market(None, None) == ("us", "default")
    assert marketface.resolve_market("zz", None) == ("us", "default")


def test_endpoint_defaults_to_us_and_lists_markets(client):
    body = client.get("/api/market").json()
    assert body["market_id"] == "us" and body["market_source"] == "default"
    assert body["market"]["currency"] == "USD"
    assert {m["id"] for m in body["markets"]} == set(marketface.MARKETS)


def test_endpoint_stored_choice_is_reported_as_choice(client):
    body = client.get("/api/market?market=gb").json()
    assert body["market_id"] == "gb" and body["market_source"] == "choice"
    assert client.get("/api/market?market=nope").json()["market_id"] == "us"


def test_country_header_ignored_unless_trusted(client, db):
    assert client.get("/api/market", headers={"CF-IPCountry": "GB"}).json()["market_source"] == "default"
    trusted = Settings(jwt_secret="t" * 40, trust_cf_country=True)
    with TestClient(create_app(trusted, db=db)) as c:
        body = c.get("/api/market", headers={"CF-IPCountry": "AU"}).json()
        assert (body["market_id"], body["market_source"]) == ("au", "detected")
        body = c.get("/api/market?market=ca", headers={"CF-IPCountry": "AU"}).json()
        assert (body["market_id"], body["market_source"]) == ("ca", "choice")
