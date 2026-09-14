"""Collector: eBay Browse API across US, UK, DE and AU marketplaces.

Searches each marketplace's WHOLE-VEHICLE category for the marque, then
filters locally for 620s. Fetch and parse are split so tests can run the
parser against saved fixture responses.

The category scoping is the load-bearing part — see MARKETPLACES for the
2026-09-14 diagnosis of why an unscoped keyword search returned zero
records every day for a month. Parts-era defences are kept for the
unscoped path because the fixtures and regression tests still exercise
it, and because an unscoped rescue query may return one day.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620, RE_OTHER_GEN
from listings.ebay_auth import mint_token

SOURCE = "ebay"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# (marketplace, country, whole-vehicle category id). The category is the
# whole point: 2026-09-14 diagnosis found the collector had returned zero
# records every day since it shipped because an UNSCOPED keyword search
# drowns in parts — "datsun 620" matches ~8,800 items on EBAY_US and the
# API caps a page at 200, every one of which was a bumper, a Hot Wheels
# car or a vintage advert. Not one whole vehicle appeared in ~1,800 items
# sampled across four marketplaces, so no filter change could ever have
# helped: the trucks were never in the payload.
#
# Scoped to the vehicle category the picture is sane and small — 28 Datsun
# vehicles on EBAY_US, 3 on EBAY_AU — which local filtering can handle.
# Category ids are per-site and were verified live (data/research/
# ebay-categories.json). US 6001 and AU 29690 returned whole cars and are
# proven. GB 9801 and DE 9801 are the sites' car nodes but returned 0 and
# 3 Datsun items respectively, so they are unproven rather than wrong —
# do NOT "fix" them to the high-volume candidates the research file shows
# (GB 31853, DE 29690): those scored well only because the round-4
# vehicle heuristic wanted a year-led title, and sales brochures and Hot
# Wheels boxes are titled exactly that way.
MARKETPLACES = [
    ("EBAY_US", "US", "6001"),
    ("EBAY_GB", "GB", "9801"),
    ("EBAY_DE", "DE", "9801"),
    ("EBAY_AU", "AU", "29690"),
]
# Broad marque queries inside the vehicle category. "datsun 620" is NOT
# used: Motors titles are built from year/make/model and a 620 is often
# titled "1978 Datsun Pickup", so the model code alone would miss it.
# The category keeps the result set small enough to filter locally.
QUERIES = ["datsun"]
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

# --- vehicle-scoped admission ------------------------------------------
# Motors builds a vehicle title from the seller's year/make/model fields,
# so a 620 can reach us as "1978 Datsun Pickup" with no model code at all.
# That is not theory: inside the vehicle category q="datsun 620" returned
# total=0 on all four marketplaces while the category itself held real
# Datsun cars ("1970 Datsun 521 Pickup"). Requiring "620" in the title
# would therefore keep the collector half-blind even after the category
# fix. Inside the category the entire marque is only ~30 listings
# worldwide, so a model-less Datsun pickup of 620 vintage is admitted for
# the owner to screen — the standing instruction since 2026-07-17 is to
# show all 620 variants rather than risk filtering a real truck away.
_PICKUP_RE = re.compile(r"pick[\s-]?up|\btrucks?\b|\butes?\b|pritsche", re.I)

# Datsun nameplates that settle the question the other way: if the title
# names one of these it is not an unidentified pickup. RE_OTHER_GEN
# already covers the neighbouring truck generations (520/521/720/D21).
_NOT_620_MODEL_RE = re.compile(
    r"\b\d{3}ZX?\b|\b(?:510|610|710|810|910|1200|1300|1600|2000|240K"
    r"|B1?[123]0|B210|B310)\b|bluebird|sunny|cedric|fairlady|roadster"
    r"|skyline|violet|cherry|patrol|cabstar|urvan|homer|hardbody|navara"
    r"|frontier|stanza|maxima|laurel|gloria|silvia|vanette|prairie", re.I)

# 620 production ran 1972-1979; a year either side covers registration
# dates and sellers who round. A Motors vehicle listing always carries a
# year, so a pickup with no recognisable year is too vague to admit.
_YEAR_MIN, _YEAR_MAX = 1971, 1980


def _unidentified_620_pickup(title: str) -> bool:
    """A Datsun pickup of 620 vintage whose title names no model at all."""
    if not re.search(r"datsun|nissan", title, re.I):
        return False
    if not _PICKUP_RE.search(title):
        return False
    if _NOT_620_MODEL_RE.search(title):
        return False
    year = normalize.extract_year(title)
    return year is not None and _YEAR_MIN <= year <= _YEAR_MAX


def is_620_title(title: str, vehicle_scoped: bool = False) -> bool:
    """The model-identity rule, shared by parse_items and the self-test."""
    if RE_OTHER_GEN.search(title):
        return False
    if RE_620.search(title):
        return True
    # Model-less admission only inside the vehicle category: in an
    # unscoped payload "1978 Datsun Pickup" is as likely a brochure cover.
    return vehicle_scoped and _unidentified_620_pickup(title)


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


def parse_items(payload: dict, marketplace_country: str, fx_day: dict,
                vehicle_scoped: bool = False) -> list[dict]:
    """Filter and normalise one marketplace's Browse search response.

    vehicle_scoped: the request was restricted to the marketplace's whole-
    vehicle category, so the parts word list and the price floor are
    skipped — the category already did that work, and both would other-
    wise cost real trucks ("...new fender flares", a £1 opening bid).
    Same division of labour as the Yahoo Auctions collector.
    """
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
        if not is_620_title(title, vehicle_scoped):
            continue
        if not vehicle_scoped and _looks_like_part(title, categories):
            continue

        price_block = it.get("price") or {}
        amount = float(price_block["value"]) if price_block.get("value") else None
        currency = price_block.get("currency", "USD")

        # A fixed-price whole vehicle is never $12; cheap Buy-It-Nows are
        # memorabilia that dodged the word/category nets (2026-07-17 escapee:
        # an $11.99 'Vintage Ad' served without category data). Auctions are
        # exempt: real trucks legitimately start at low opening bids.
        buying = it.get("buyingOptions") or []
        if not vehicle_scoped and "FIXED_PRICE" in buying and "AUCTION" not in buying \
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
        for marketplace, country, category in MARKETPLACES:
            # One failing marketplace must not take down the other three.
            try:
                for query in QUERIES:
                    resp = client.get(
                        SEARCH_URL,
                        params={"q": query, "limit": LIMIT,
                                "category_ids": category},
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-EBAY-C-MARKETPLACE-ID": marketplace,
                        },
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    raw_total += len(payload.get("itemSummaries", []))
                    for rec in parse_items(payload, country, fx_day,
                                           vehicle_scoped=True):
                        if rec["id"] not in seen:  # items repeat across queries/marketplaces
                            seen.add(rec["id"])
                            records.append(rec)
            except Exception as exc:
                failures.append(f"{marketplace}: {exc}")
    if failures and len(failures) == len(MARKETPLACES):
        raise RuntimeError(f"all marketplaces failed ({failures[0]})")
    if failures:
        print(f"ebay: partial failure, continuing without {failures}")
    # Canary: the vehicle category always holds Datsun cars somewhere (28 on
    # EBAY_US, 3 on EBAY_AU when measured), so zero raw items across EVERY
    # marketplace means auth broke or a category id moved — the failure that
    # masqueraded as "ok, no 620s today" for a month. Zero RECORDS is not an
    # error: eBay genuinely had no 620 vehicle listed on diagnosis day.
    if raw_total == 0:
        raise RuntimeError(
            "canary: vehicle-category search returned zero raw items on all "
            "marketplaces (auth failure or category ids moved?)")
    return records
