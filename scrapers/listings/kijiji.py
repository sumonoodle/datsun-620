"""Collector: Kijiji (Canada), keyword search "datsun 620".

The search page is Next.js with an Apollo cache: every result is a
StandardListing:<id> entry with title, description, price (in CENTS),
location and canonical URL. The keyword results are dominated by Hot
Wheels diecast, so the vehicle gate is structural: a real truck's URL
lives under /v-cars-trucks/ or /v-classic-cars/, toys under /v-toys-games/
— no word list needed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "kijiji"
URL = "https://www.kijiji.ca/b-canada/datsun-620/k0l0"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-CA,en;q=0.9",
}

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)
_VEHICLE_PATHS = ("/v-cars-trucks/", "/v-classic-cars/", "/v-autos-camions/")
_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = (data.get("props", {}).get("pageProps", {}) or {}).get("__APOLLO_STATE__") or {}
    listings = [v for k, v in apollo.items() if k.startswith("StandardListing:")]
    if not listings:
        raise ValueError("zero listings in Apollo cache (payload moved?)")

    records = []
    for l in listings:
        url = l.get("url") or ""
        title = l.get("title") or ""
        desc = l.get("description") or ""
        listing_id = str(l.get("id") or "")
        if not listing_id:
            continue
        if not any(p in url for p in _VEHICLE_PATHS):
            continue  # toys, books and parts live under other paths
        kc = king_cab.check(title, desc)
        if not kc["matched"]:
            continue
        if not (_620_RE.search(title) or _620_RE.search(desc)):
            continue

        price_block = l.get("price") or {}
        cents = price_block.get("amount")
        amount = round(cents / 100, 2) if isinstance(cents, (int, float)) else None
        location = (l.get("location") or {}).get("name")
        images = [u for u in (l.get("imageUrls") or [])[:1] if u]

        records.append({
            "id": f"kijiji:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(url),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": normalize.extract_year(f"{title} {desc}"),
            "country": "CA",
            "region": location,
            "drive_side": normalize.infer_drive_side("CA", f"{title} {desc}"),
            "king_cab": kc,
            "price": normalize.make_price(amount, "CAD", fx_day),
            "images": images,
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
