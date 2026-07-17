"""Collector: ClassicCars.com, model-scoped Datsun 620 search.

The search page embeds one JSON-LD block per listing (@type "car") with
name, sku, description, offer price and image — no HTML scraping needed
beyond extracting the blocks. The search is already scoped to the 620
model, so the King Cab filter is the only gate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "classiccars"
BASE = "https://classiccars.com"
URL = f"{BASE}/listings/find/all-years/datsun/620"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

_LD_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
# Listing URLs end "...-for-sale-in-cadillac-michigan-49601".
_PLACE_RE = re.compile(r"-for-sale-in-([a-z-]+)-(\d{5})?$")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    records = []
    seen: set[str] = set()
    found_car_block = False
    for m in _LD_RE.finditer(html):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("@type") != "car":
            continue
        found_car_block = True

        sku = d.get("sku", "")
        name = d.get("name", "")
        desc = d.get("description", "")
        offer = d.get("offers") or {}
        if not sku or sku in seen:
            continue
        kc = king_cab.check(name, desc)
        if not kc["matched"]:
            continue
        seen.add(sku)

        path = offer.get("url") or ""
        region = None
        pm = _PLACE_RE.search(path)
        if pm:
            region = pm.group(1).replace("-", " ").title()
        try:
            amount = float(offer["price"]) if offer.get("price") else None
        except (ValueError, TypeError):
            amount = None
        year = None
        if str(d.get("modelDate", "")).isdigit():
            y = int(d["modelDate"])
            year = y if 1971 <= y <= 1980 else None
        image = (d.get("image") or {}).get("url")

        records.append({
            "id": f"classiccars:{sku}",
            "source": SOURCE,
            "source_listing_id": sku,
            "url": normalize.safe_url(BASE + path if path.startswith("/") else path),
            "title": name,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": year or normalize.extract_year(name),
            "country": "US",
            "region": region,
            "drive_side": normalize.infer_drive_side("US", f"{name} {desc}"),
            "king_cab": kc,
            "price": normalize.make_price(amount, offer.get("priceCurrency") or "USD", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    if not found_car_block:
        # The model page always carries JSON-LD when listings exist; none at
        # all more likely means a layout change than an empty market, but an
        # empty market IS possible for a rare truck — so only raise when the
        # page doesn't even look like the search page.
        if "datsun" not in html.lower():
            raise ValueError("page does not look like the 620 search (blocked or moved?)")
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
