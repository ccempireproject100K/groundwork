"""The visitor's market face (owner ruling 2026-11-01).

No page silently wears a non-US face. The precedence is:

  1. the visitor's stored choice (the app keeps it in the browser and sends
     it as the ``market`` parameter),
  2. then the edge's detected country (Cloudflare's CF-IPCountry header),
     only when GW_TRUST_CF_COUNTRY is on and the country has a face here,
  3. then the US default.

Plans live in tiers.py and are in US dollars only. A non-US face changes
wording and formats (the phone example) and says plainly that prices are in
US dollars (USD). It never shows a converted price. Detection never locks:
the switcher stays visible on every page. The crisis surfaces (988 and 911)
are not part of the face and never change with it.
"""
DEFAULT_MARKET = "us"
CURRENCY = "USD"

MARKETS: dict[str, dict] = {
    "us": {"name": "United States", "flag": "\U0001F1FA\U0001F1F8", "phone_example": "(512) 555-0142"},
    "ca": {"name": "Canada", "flag": "\U0001F1E8\U0001F1E6", "phone_example": "(416) 555-0142"},
    "gb": {"name": "United Kingdom", "flag": "\U0001F1EC\U0001F1E7", "phone_example": "020 7946 0142"},
    "au": {"name": "Australia", "flag": "\U0001F1E6\U0001F1FA", "phone_example": "02 5550 0142"},
}

_COUNTRY_TO_MARKET = {"US": "us", "CA": "ca", "GB": "gb", "UK": "gb", "AU": "au"}


def market_for_country(country: str | None) -> str | None:
    """A detected country mapped to a face we have, else None. Sentinels
    (XX, T1) and countries without a face fall through to the default."""
    if not country:
        return None
    return _COUNTRY_TO_MARKET.get(country.strip().upper())


def normalize_choice(choice: str | None) -> str | None:
    value = (choice or "").strip().lower()
    return value if value in MARKETS else None


def resolve_market(choice: str | None, country: str | None) -> tuple[str, str]:
    """(market id, source) with source one of choice, detected, default."""
    picked = normalize_choice(choice)
    if picked:
        return picked, "choice"
    detected = market_for_country(country)
    if detected:
        return detected, "detected"
    return DEFAULT_MARKET, "default"


def face_payload(choice: str | None, cf_country: str | None, trust_cf_country: bool) -> dict:
    market_id, source = resolve_market(choice, cf_country if trust_cf_country else None)
    face = MARKETS[market_id]
    return {
        "market_id": market_id,
        "market_source": source,
        "market": {"id": market_id, "name": face["name"], "flag": face["flag"],
                   "phone_example": face["phone_example"], "currency": CURRENCY},
        "markets": [{"id": k, "name": v["name"], "flag": v["flag"]} for k, v in MARKETS.items()],
    }
