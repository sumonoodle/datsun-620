"""Hilux collector: Kijiji (Canada), keyword search "toyota hilux".

Same Next.js/Apollo page as the 620 collector (listings/kijiji.py), with
one difference that matters: on the 2026-09-24 probe page every vehicle
was an AutosListing:<id> entry, not StandardListing:<id>. StandardListing
now holds only the toys, manuals and parts (20 Matchbox/Hot Wheels ads,
a 1976 Hi-Lux shop manual, tail-light lenses); the ten real trucks under
/v-cars-trucks/ were all AutosListing. Both types are read here.
AutosListing prices are in cents like StandardListing's, and it carries
structured attributes (caryear, carfueltype) that classify() uses.

The /v-cars-trucks/ path gate (from the 620 collector) is what keeps the
toys out. classify() alone would keep "1980 Toyota Hilux 'Minitrek' 1981
Hot Wheels" and "Matching pair 1977-1983 Toyota Pickup Tail Light
Lenses", both on the probe page.

The US-name probe, "toyota pickup 1981", returned "No results" on
2026-09-24 (a 200 page with totalCount 0), so it is not polled; a broader
US-name search is waiting on a second probe round.

The guard reads the search's own totalCount: zero is an empty market and
returns nothing; results promised with no listing parsed raises.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.kijiji import HEADERS, _NEXT_RE, _VEHICLE_PATHS

SOURCE = "kijiji"
URL = "https://www.kijiji.ca/b-canada/toyota-hilux/k0l0"
_LISTING_TYPES = ("StandardListing:", "AutosListing:")


def _total_count(apollo: dict) -> int | None:
    """The search's totalCount, or None when the page does not say."""
    root = apollo.get("ROOT_QUERY") or {}
    for key, val in root.items():
        if key.startswith("searchResultsPage") and isinstance(val, dict):
            count = (val.get("pagination") or {}).get("totalCount")
            if isinstance(count, int):
                return count
    return None


def _attrs(listing: dict) -> dict[str, str]:
    out = {}
    for a in ((listing.get("attributes") or {}).get("all") or []):
        vals = a.get("canonicalValues") or []
        if a.get("canonicalName") and vals:
            out[a["canonicalName"]] = str(vals[0])
    return out


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = (data.get("props", {}).get("pageProps", {}) or {}).get("__APOLLO_STATE__") or {}
    listings = [v for k, v in apollo.items() if k.startswith(_LISTING_TYPES)]
    total = _total_count(apollo)
    if not listings:
        if total == 0:
            return []  # the search says it is empty: an empty market
        raise ValueError("zero listings in Apollo cache (payload moved?)")

    records = []
    seen: set[str] = set()
    for l in listings:
        url = l.get("url") or ""
        title = l.get("title") or ""
        desc = l.get("description") or ""
        listing_id = str(l.get("id") or "")
        if not listing_id or listing_id in seen:
            continue
        if not any(p in url for p in _VEHICLE_PATHS):
            continue  # toys, books and parts live under other paths
        attrs = _attrs(l)
        year = int(attrs["caryear"]) if attrs.get("caryear", "").isdigit() else None
        # The structured fuel type goes to classify() as text so its diesel
        # rule sees it ("gas" is its petrol counter-signal).
        fuel = f" fuel: {attrs['carfueltype']}" if attrs.get("carfueltype") else ""
        ident = hilux.classify(title, desc + fuel, year=year)
        if ident is None:
            continue
        seen.add(listing_id)

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
            "year": ident["year"],
            "country": "CA",
            "region": location,
            "drive_side": normalize.infer_drive_side("CA", f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "CAD", fx_day),
            "images": images,
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
