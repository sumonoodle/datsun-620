"""Hilux collector: eBay (Browse API), whole-vehicle categories only.

Reuses the 620 collector's marketplaces, category ids and auth (see
listings/ebay.py for why the category scoping is non-negotiable). What
differs is the query. "toyota hilux" alone would be useless: the vehicle
category holds hundreds of modern Hiluxes on EBAY_GB and EBAY_AU and the
API caps a page at 200, so a 1980 truck could fall off the end. Motors
titles are built from year/make/model, so a year-led query pins the
generation server-side and each result set stays small.

The US never used the Hilux name ("Toyota Pickup"/"Truck"), so both
names are queried for every year of the generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.ebay import MARKETPLACES, SEARCH_URL
from listings.ebay_auth import mint_token

SOURCE = "ebay"
LIMIT = 200
QUERIES = ([f"{y} toyota hilux" for y in range(1978, 1985)]
           + [f"{y} toyota pickup" for y in range(1979, 1984)]
           + ["hilux rn30", "hilux rn34", "hilux rn40", "hilux 12r"])


def parse_items(payload: dict, marketplace_country: str, fx_day: dict) -> list[dict]:
    records = []
    for it in payload.get("itemSummaries", []):
        title = it.get("title", "")
        desc = it.get("shortDescription", "")
        # Title first: a modern Hilux ad may describe the classic it replaces.
        ident = hilux.classify(title, desc)
        if ident is None:
            continue
        item_id = it.get("legacyItemId") or it.get("itemId", "")
        if not item_id:
            continue
        price_block = it.get("price") or {}
        amount = float(price_block["value"]) if price_block.get("value") else None
        country = normalize.to_country_code(
            (it.get("itemLocation") or {}).get("country") or marketplace_country)
        image = (it.get("image") or {}).get("imageUrl")
        records.append({
            "id": f"ebay:{item_id}",
            "source": SOURCE,
            "source_listing_id": str(item_id),
            "url": normalize.safe_url(it.get("itemWebUrl")),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": country,
            "region": (it.get("itemLocation") or {}).get("stateOrProvince"),
            "drive_side": normalize.infer_drive_side(country, f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, price_block.get("currency", "USD"), fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    token = mint_token()
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    raw_total = 0
    with httpx.Client(timeout=30) as client:
        for marketplace, country, category in MARKETPLACES:
            try:
                for query in QUERIES:
                    resp = client.get(
                        SEARCH_URL,
                        params={"q": query, "limit": LIMIT, "category_ids": category},
                        headers={"Authorization": f"Bearer {token}",
                                 "X-EBAY-C-MARKETPLACE-ID": marketplace},
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    raw_total += len(payload.get("itemSummaries", []))
                    for rec in parse_items(payload, country, fx_day):
                        if rec["id"] not in seen:
                            seen.add(rec["id"])
                            records.append(rec)
            except Exception as exc:
                failures.append(f"{marketplace}: {exc}")
    if failures and len(failures) == len(MARKETPLACES):
        raise RuntimeError(f"all marketplaces failed ({failures[0]})")
    if failures:
        print(f"ebay (hilux): partial failure, continuing without {failures}")
    # Canary: Toyota pickups of this era are common enough on eBay Motors
    # that zero raw items across every marketplace and every query means
    # auth or the categories broke, not an empty market.
    if raw_total == 0:
        raise RuntimeError("canary: zero raw items across all Hilux queries")
    return records
