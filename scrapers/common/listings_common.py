"""Shared helpers for listing collectors: drive-side inference, id slugs,
year parsing, and turning a raw record into a scored, schema-shaped listing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date

from common import king_cab
from common.fx import to_gbp


@dataclass
class ListingResult:
    """What a listing collector returns: raw records plus success/skip status.
    A blocked source or missing credentials reports ok=False with a note so the
    run continues and the digest can flag the skip."""

    source: str
    ok: bool
    records: list[dict] = dc_field(default_factory=list)
    note: str = ""

# Right-hand-drive markets (ISO alpha-2). Everything else defaults to LHD.
RHD_COUNTRIES = {"JP", "GB", "UK", "AU", "ZA", "NZ", "IE", "IN", "TH", "HK", "SG", "MY"}
COUNTRY_NAMES = {"US": "United States", "JP": "Japan", "GB": "United Kingdom", "UK": "United Kingdom",
                 "AU": "Australia", "ZA": "South Africa", "DE": "Germany", "CA": "Canada", "NZ": "New Zealand"}


def infer_drive_side(country_code: str | None) -> tuple[str, bool]:
    """Return (drive_side, inferred). Inferred is always True here since we
    deduce from country, never an explicit field."""
    if not country_code:
        return "unknown", True
    return ("RHD" if country_code.upper() in RHD_COUNTRIES else "LHD"), True


def parse_year(*texts: str) -> int | None:
    for t in texts:
        if not t:
            continue
        m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", t)
        if m:
            return int(m.group(1))
    return None


def slug_id(source: str, source_url: str) -> str:
    tail = re.sub(r"[^a-z0-9]+", "-", source_url.lower().rstrip("/").split("/")[-1])[:60]
    return f"{source}-{tail}" if tail else f"{source}-{abs(hash(source_url)) % 10**8}"


def build_listing(raw: dict, fx: dict, today: str | None = None) -> dict:
    """Normalise a collector's raw record into a schema-shaped listing, applying
    FX and King Cab scoring. `raw` carries: source, source_url, title, price_original,
    currency, country_code, year, photo_urls, status, description (optional)."""
    today = today or date.today().isoformat()
    cc = raw.get("country_code")
    drive_side, inferred = infer_drive_side(cc)
    kc_score, signals = king_cab.score(raw.get("title", ""), raw.get("description", ""))
    price = raw.get("price_original")
    currency = raw.get("currency")
    gbp = to_gbp(price, currency, fx)
    return {
        "id": raw.get("id") or slug_id(raw["source"], raw["source_url"]),
        "source": raw["source"],
        "source_url": raw["source_url"],
        "title": raw.get("title", ""),
        "price_original": price,
        "currency": currency,
        "price_gbp": gbp,
        "fx_rate_used": fx.get("rates", {}).get((currency or "").upper()) if currency else None,
        "fx_date": fx.get("date"),
        "country": COUNTRY_NAMES.get((cc or "").upper(), cc),
        "region": raw.get("region"),
        "drive_side": drive_side,
        "drive_side_inferred": inferred,
        "year": raw.get("year") or parse_year(raw.get("title", "")),
        "trim": raw.get("trim"),
        "mileage": raw.get("mileage"),
        "mileage_unit": raw.get("mileage_unit"),
        "condition_notes": raw.get("condition_notes"),
        "king_cab_score": kc_score,
        "king_cab_signals": signals,
        "photo_urls": raw.get("photo_urls", []),
        "first_seen": today,
        "last_seen": today,
        "price_history": [{"date": today, "price_original": price, "price_gbp": gbp}],
        "status": raw.get("status", "active"),
        "relisted_from": None,
    }
