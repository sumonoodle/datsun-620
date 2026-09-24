"""Hilux collector: Kijiji (Canada), three category-scoped searches.

Same Next.js/Apollo page as the 620 collector (listings/kijiji.py), with
one difference that matters: on the 2026-09-24 probe pages every vehicle
was an AutosListing:<id> entry, not StandardListing:<id> (which now holds
toys, manuals and parts). Both types are read here. AutosListing prices
are in cents like StandardListing's, and it carries structured attributes
(caryear, carfueltype, carmodel) that are used below.

Searches (second probe round, 2026-09-24; the first round's all-category
keyword page was 30 of 40 toys and parts):
- Cars & Trucks, "toyota hilux": the same 10 trucks as the all-category
  search with none of the toys. No 3rd-gen on the day.
- Cars & Trucks, "toyota pickup": 1,147 results, 46 a page, and page 1
  held two real 3rd-gen trucks, "1982 Toyota 4X4 pickup project" and
  "1983 Toyota 4x4 Pickup". Canada used the US name; this is the search
  that finds them.
- Classic Cars, "toyota": 46 results (all on one page) and a real "1980
  toyota pickup", which Kijiji's model picker had filed as a Tacoma.

The /v-cars-trucks/ + /v-classic-cars/ path gate from the 620 collector
stays, for toys and parts. A second structural gate uses the seller's
model pick (carmodel): the classic page's "1982 Toyota Corolla SR5"
satisfies classify()'s US-name rule ("Toyota ... SR5"), and carmodel
"corolla" says what it is. The 3rd-gen trucks seen were filed as
othrpkups (1982, 1983) and tacoma (1980); othrmdl and t100 are the
other truck-plausible picks. A listing with no carmodel is not gated.

The guard reads each search's own totalCount: zero is an empty market and
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
URLS = [
    "https://www.kijiji.ca/b-cars-trucks/canada/toyota-hilux/k0c174l0",
    "https://www.kijiji.ca/b-cars-trucks/canada/toyota-pickup/k0c174l0",
    "https://www.kijiji.ca/b-classic-cars/canada/toyota/k0c122l0",
]
# Seller-picked models a 3rd-gen truck has been, or plausibly would be,
# filed under (see the docstring for the evidence).
_TRUCK_MODELS = {"othrpkups", "othrmdl", "tacoma", "t100"}
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
        if attrs.get("carmodel") and attrs["carmodel"] not in _TRUCK_MODELS:
            continue  # a Corolla SR5 is not a Toyota Pickup SR5
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
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for url in URLS:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day):
                    if rec["id"] not in seen:  # a truck can match two searches
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{url.split('/canada/', 1)[-1]}: {exc}")
    if failures and len(failures) == len(URLS):
        raise RuntimeError(f"all Kijiji searches failed ({failures[0]})")
    if failures:
        print(f"kijiji (hilux): partial failure, continuing without {failures}")
    return records
