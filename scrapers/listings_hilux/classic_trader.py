"""Hilux collector: Classic Trader (UK edition), the Toyota Hilux model page.

Classic Trader is a classic-only marketplace (Germany-based, pan-European,
native GBP on the /uk/ edition), so its model page carries no modern-truck
flood: everything on it is an old vehicle. It is Astro, and each result is
an <astro-island> whose `props` attribute holds the whole ad as Astro's
serialised JSON ([0, value] for a value, [1, [...]] for an array):
id, state, title, titleBySeller, yearOfProduction, price (converted and
original), location.countryCode, images and a vehicle block with
make/model slugs and body type.

2026-09-24 probe: "Toyota Hilux (0 offers)", so nothing is for sale now.
The page still shows 14 "listing references" (5 expired, 9 sold, back to
2019) in the same ResultPageCarData island, among them a 1983 Hilux 4WD
SR5 and a 1977 RN28 SR5, which is the site's Hilux history: roughly one
old Hilux a year, a few of them 3rd-gen. Low volume, zero noise, and the
UK/EU classic trade is exactly where the owner's kind of truck is sold.

Only live ads become records. Round-3 probe (the Toyota make page,
/uk/cars/search/toyota: 41 offers, 15 on page 1) confirmed the live shape:
state "published", a full canonicalUrl of the form
/uk/cars/listing/<make>/<model>/<model-spec>/<year>/<id>, and the same
ResultPageCarData island as the references. Each live ad is ALSO carried
by a BookmarkAd island, so ads are de-duplicated by id. Dead states are
listed rather than "published" required, so a new live-state name is
still read (and a count with no live ad still raises).

Guard: the search dialog island states searchResultsCount. Zero is an
empty market. A positive count with no live ad parsed raises, so a live
card in a different island shape fails loudly instead of reading as
"no Hilux".
"""

from __future__ import annotations

import html as html_lib
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "classic_trader"
BASE = "https://www.classic-trader.com"
URL = f"{BASE}/uk/cars/search/toyota/hilux"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_ISLAND_RE = re.compile(r"<astro-island\b([^>]*)>")
_PROPS_RE = re.compile(r'\bprops="([^"]*)"')
_DEAD_STATES = {"expired", "sold", "deleted", "inactive", "withdrawn", "archived"}


def _astro(value):
    """Decode Astro's island serialisation: [0, v] is a value (objects are
    decoded key by key), [1, [...]] an array; a bare [0] is undefined."""
    if isinstance(value, list) and value and value[0] in (0, 1) and len(value) <= 2:
        if len(value) == 1:
            return None
        tag, inner = value
        if tag == 1 and isinstance(inner, list):
            return [_astro(v) for v in inner]
        return _astro(inner)
    if isinstance(value, dict):
        return {k: _astro(v) for k, v in value.items()}
    return value


def _islands(html: str) -> list[dict]:
    out = []
    for m in _ISLAND_RE.finditer(html):
        p = _PROPS_RE.search(m.group(1))
        if not p:
            continue
        try:
            out.append(_astro(json.loads(html_lib.unescape(p.group(1)))))
        except ValueError:
            continue
    return out


def _listing_url(ad: dict) -> str:
    canonical = ad.get("canonicalUrl")
    if isinstance(canonical, str) and canonical.startswith("http"):
        return canonical
    if isinstance(canonical, str) and canonical.startswith("/"):
        return f"{BASE}{canonical}"
    # No canonical link on the card: the site's listing path shape,
    # /uk/cars/listing/<make>/<model>/<model-spec>/<year>/<id>.
    v = ad.get("vehicle") or {}
    make = (v.get("make") or {}).get("slug") or "toyota"
    model = (v.get("model") or {}).get("slug") or "hilux"
    spec = (v.get("modelSpecification") or {}).get("slug") or model
    return f"{BASE}/uk/cars/listing/{make}/{model}/{spec}/{ad.get('yearOfProduction')}/{ad.get('id')}"


def parse_page(html: str, fx_day: dict) -> list[dict]:
    islands = _islands(html)
    if not islands:
        raise ValueError("no Astro islands (page layout changed or blocked?)")
    count = None
    ads: dict[str, dict] = {}
    for props in islands:
        if isinstance(props.get("searchResultsCount"), int):
            count = props["searchResultsCount"]
        ad = props.get("vehicleAd")
        if isinstance(ad, dict) and ad.get("id") is not None:
            ads.setdefault(str(ad["id"]), ad)
    if count is None:
        raise ValueError("searchResultsCount missing (search dialog moved?)")

    live = [ad for ad in ads.values() if str(ad.get("state") or "").lower() not in _DEAD_STATES]
    if count and not live:
        raise ValueError(f"search reports {count} offers but no live ad was parsed")

    records = []
    for ad in live:
        ad_id = str(ad["id"])
        vehicle = ad.get("vehicle") or {}
        model = ((vehicle.get("model") or {}).get("label") or "")
        make = ((vehicle.get("make") or {}).get("label") or "")
        if make and make.lower() != "toyota":
            continue
        # Structural model gate: the Hilux URL is scoped server-side, but a
        # make-wide page (Land Cruiser BJ42s, FJ45s on the round-3 Toyota
        # page) must never reach classify() with require_name=False.
        model_slug = ((vehicle.get("model") or {}).get("slug") or "hilux").lower()
        if model_slug != "hilux":
            continue
        title_std = ad.get("title") or ""            # "1984 | Toyota Hilux"
        seller_title = ad.get("titleBySeller") or ""  # "Type pol N46"
        title = seller_title if model.lower() in seller_title.lower() else (
            f"{title_std.replace(' | ', ' ')} {seller_title}".strip())
        year = ad.get("yearOfProduction") if isinstance(ad.get("yearOfProduction"), int) else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        body = ((vehicle.get("bodyDetailed") or vehicle.get("body") or {}).get("label"))
        # Scoped to the Hilux model server-side, so the seller's own title
        # need not name it ("Type pol N46" on the probe page).
        ident = hilux.classify(title, f"{title_std} {model}", year=year,
                               require_name=False, body_style=body)
        if ident is None:
            continue

        price = ad.get("price") or {}
        on_request = price.get("isOnRequest") or price.get("isAuctionSale")
        # The seller's own currency and amount, not the site's GBP conversion
        # (make_price converts at the pipeline's rate of the day).
        amount = price.get("originalAmount")
        currency = price.get("originalCurrency") or price.get("currency") or "GBP"
        if on_request or not isinstance(amount, (int, float)):
            amount = None
        country = normalize.to_country_code((ad.get("location") or {}).get("countryCode"))
        images = []
        for img in ad.get("images") or []:
            url = (img or {}).get("originalImageUrl")
            if url:
                images.append(url)
                break

        records.append({
            "id": f"classic_trader:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(_listing_url(ad)),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": country,
            "region": (ad.get("location") or {}).get("city") or None,
            "drive_side": normalize.infer_drive_side(country, title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(float(amount) if amount is not None else None,
                                          currency, fx_day),
            "images": images,
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
