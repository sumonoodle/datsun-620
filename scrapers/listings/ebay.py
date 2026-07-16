"""Collector: eBay Browse API across US, UK, DE and AU marketplaces.

Searches broadly for "datsun 620", then applies the strict King Cab filter
plus a parts/toys exclusion (category path and keyword based). Fetch and parse
are split so tests can run the parser against saved fixture responses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from listings.ebay_auth import mint_token

SOURCE = "ebay"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
MARKETPLACES = [
    ("EBAY_US", "US"),
    ("EBAY_GB", "GB"),
    ("EBAY_DE", "DE"),
    ("EBAY_AU", "AU"),
]
# Broad query for coverage plus targeted queries for recall: the broad search
# returns thousands of parts hits and the API caps a page at 200 results, so
# a genuine King Cab vehicle could sit beyond the window. The targeted terms
# put any real King Cab listing at the top of its own result set.
QUERIES = ["datsun king cab", "datsun 620 king cab", "datsun 620"]
LIMIT = 200

# Titles matching King Cab terms but clearly not whole vehicles.
_PARTS_WORDS = [
    "for datsun", "fits datsun", "fit datsun", "carburetor", "carb ", "fender",
    "grille", "emblem", "badge", "decal", "sticker", "brochure", "manual",
    "toy", "diecast", "die-cast", "1/64", "1/24", "1:24", "1:64", "model kit",
    "keychain", "mug", "t-shirt", "shirt", "poster", "tail light", "taillight",
    "headlight", "bumper", "mirror", "door handle", "weatherstrip", "seal kit",
    "gasket", "bearing", "brake", "clutch", "radiator", "tailgate",
]


def _looks_like_part(title: str, categories: list[str]) -> bool:
    t = (title or "").lower()
    if any(w in t for w in _PARTS_WORDS):
        return True
    cats = " ".join(categories).lower()
    return "parts" in cats or "accessories" in cats or "toys" in cats


def parse_items(payload: dict, marketplace_country: str, fx_day: dict) -> list[dict]:
    """Filter and normalise one marketplace's Browse search response."""
    records = []
    for it in payload.get("itemSummaries", []):
        title = it.get("title", "")
        desc = it.get("shortDescription", "")
        categories = [c.get("categoryName", "") for c in it.get("categories", [])]

        kc = king_cab.check(title, desc)
        if not kc["matched"]:
            continue
        if _looks_like_part(title, categories):
            continue

        price_block = it.get("price") or {}
        amount = float(price_block["value"]) if price_block.get("value") else None
        currency = price_block.get("currency", "USD")

        country = normalize.to_country_code(
            (it.get("itemLocation") or {}).get("country") or marketplace_country
        )
        item_id = it.get("legacyItemId") or it.get("itemId", "")
        if not item_id:
            continue  # no stable identity, cannot track it
        image = (it.get("image") or {}).get("imageUrl")

        records.append({
            "id": f"ebay:{item_id}",
            "source": SOURCE,
            "source_listing_id": str(item_id),
            "url": it.get("itemWebUrl", ""),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc or None) if not desc or len(desc) <= 500 else desc[:500],
            "year": normalize.extract_year(title),
            "country": country,
            "region": (it.get("itemLocation") or {}).get("stateOrProvince"),
            "drive_side": normalize.infer_drive_side(country, f"{title} {desc}"),
            "king_cab": kc,
            "price": normalize.make_price(amount, currency, fx_day),
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
        for marketplace, country in MARKETPLACES:
            # One failing marketplace must not take down the other three.
            try:
                for query in QUERIES:
                    resp = client.get(
                        SEARCH_URL,
                        params={"q": query, "limit": LIMIT},
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-EBAY-C-MARKETPLACE-ID": marketplace,
                        },
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    raw_total += len(payload.get("itemSummaries", []))
                    for rec in parse_items(payload, country, fx_day):
                        if rec["id"] not in seen:  # items repeat across queries/marketplaces
                            seen.add(rec["id"])
                            records.append(rec)
            except Exception as exc:
                failures.append(f"{marketplace}: {exc}")
    if failures and len(failures) == len(MARKETPLACES):
        raise RuntimeError(f"all marketplaces failed ({failures[0]})")
    if failures:
        print(f"ebay: partial failure, continuing without {failures}")
    # Canary: "datsun 620" always has thousands of parts hits, so zero raw
    # items across every marketplace means the API or auth is broken in a way
    # that would otherwise masquerade as "ok, no King Cabs today".
    if raw_total == 0:
        raise RuntimeError("canary: broad search returned zero raw items on all marketplaces")
    return records
