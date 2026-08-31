"""Collector: eBay Browse API across US, UK, DE and AU marketplaces.

Searches broadly for "datsun 620", then applies the strict King Cab filter
plus a parts/toys exclusion (category path and keyword based). Fetch and parse
are split so tests can run the parser against saved fixture responses.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620
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

# Titles matching King Cab terms but clearly not whole vehicles. The 2026-07-17
# incident: 166 print ads, posters and Tomica toys ingested in one run.
# 2026-08-22 bug hunt: the original bare-substring matching was killing real
# trucks — "manual" hit 4-Speed Manual transmissions, "toy" hit Toyota-swap
# titles, "art" hit "partial restoration", "sign" hit "consignment". Terms
# are now word-bounded regexes, "manual" means only the printed kind, and
# service-item words real ads mention ("new brakes and clutch") are gone —
# parts listings for those are categorized and the category gate holds them.
_PARTS_TERMS = [
    r"for datsun", r"fits datsun", r"fit datsun", r"carburetor", r"\bcarb\b",
    r"fender", r"grille", r"emblem", r"badge", r"decal", r"sticker",
    r"brochure", r"(?:owner'?s?|service|repair|shop|workshop|instruction)\s+manual",
    r"\btoys?\b", r"diecast", r"die-cast", r"1/64", r"1/24", r"1:24", r"1:64",
    r"model kit", r"keychain", r"\bmug\b", r"t-shirt", r"\bshirts?\b",
    r"poster", r"tail light", r"taillight", r"headlight", r"door handle",
    r"weatherstrip", r"seal kit", r"print ad", r"advertisement", r"magazine",
    r"\bphoto\b", r"blueprint", r"\bpromo\b", r"\bart\b", r"man cave",
    r"banner", r"\bsigns?\b", r"\bpatch\b", r"keyring", r"tomica", r"tomytec",
    r"hot wheels", r"matchbox", r"1/43", r"1:43", r"greenlight",
]
_PARTS_RE = re.compile("|".join(_PARTS_TERMS), re.I)

# Category gate, per-name so a "Car & Truck Parts" node can never satisfy a
# "truck" substring. Names are localized per marketplace (EBAY_DE says
# "Autos" / "Automobile & Oldtimer"), so an UNRECOGNIZED category is not
# proof of memorabilia: the explicit denylist holds the 2026-07-17 flood
# (Collectibles/Art/Toys nodes) and anything else falls through to the
# word list and price floor.
_VEHICLE_CATEGORY_NAMES = {
    "cars & trucks", "classic cars", "automobiles", "other vehicles", "cars",
    "autos", "automobile", "automobile & oldtimer", "oldtimer", "fahrzeuge",
    "pickup", "classic cars, trucks & motorcycles",
}
_NON_VEHICLE_CAT_RE = re.compile(
    r"collectib|toys|diecast|die-cast|\bart\b|magazin|advertis|memorabilia|"
    r"parts|accessor|zubeh|teile|apparel|merchandise", re.I)

_AD_RE = re.compile(r"\bads?\b|\badvert\b", re.I)


def _looks_like_part(title: str, categories: list[str]) -> bool:
    t = (title or "").lower()
    if _PARTS_RE.search(t):
        return True
    if _AD_RE.search(t):
        return True
    names = [c.strip().lower() for c in categories if c]
    if any(n in _VEHICLE_CATEGORY_NAMES for n in names):
        return False
    if any(_NON_VEHICLE_CAT_RE.search(n) for n in names):
        return True
    return False


def parse_items(payload: dict, marketplace_country: str, fx_day: dict) -> list[dict]:
    """Filter and normalise one marketplace's Browse search response."""
    records = []
    for it in payload.get("itemSummaries", []):
        title = it.get("title", "")
        desc = it.get("shortDescription", "")
        categories = [c.get("categoryName", "") for c in it.get("categories", [])]

        # Owner decision 2026-07-17: ALL 620 variants are tracked (King Cab
        # merely highlighted downstream) — rarity means poorly-worded King
        # Cab listings must not be filtered away. kc is recorded, not gated.
        kc = king_cab.check(title, desc)
        # Title only: a 720 listing's description may well mention the 620
        # it succeeded. RE_620's comma guard keeps "6,620 Original Miles"
        # on a 720 from counting as a model reference.
        if not RE_620.search(title):
            continue
        if _looks_like_part(title, categories):
            continue

        price_block = it.get("price") or {}
        amount = float(price_block["value"]) if price_block.get("value") else None
        currency = price_block.get("currency", "USD")

        # A fixed-price whole vehicle is never $12; cheap Buy-It-Nows are
        # memorabilia that dodged the word/category nets (2026-07-17 escapee:
        # an $11.99 'Vintage Ad' served without category data). Auctions are
        # exempt: real trucks legitimately start at low opening bids.
        buying = it.get("buyingOptions") or []
        if "FIXED_PRICE" in buying and "AUCTION" not in buying \
                and amount is not None and amount < 500:
            continue

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
            "url": normalize.safe_url(it.get("itemWebUrl")),
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
