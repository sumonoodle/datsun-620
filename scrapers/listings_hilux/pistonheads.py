"""Hilux collector: PistonHeads (UK), the Toyota Hilux model page.

Same Next.js/Apollo page as the 620 collector (listings/pistonheads.py):
Advert:<id> entities with headline, native GBP price, year and a
specificationData block. /buy/toyota/hilux is scoped to the model
server-side, so titles need not name it (require_name=False).

The catch: the page shows 16 adverts of 293 (2026-09-24 probe), ordered
by PistonHeads' own promotion, so a 1980 truck could sit on page 12. The
same Apollo cache carries the refine panel's Year facet, which counts
EVERY Hilux advert by year: on the probe day it started at 1992 (one
advert), so no 3rd-gen truck was listed anywhere in the search. That
facet is the guard. When it counts 1978-1984 adverts that page 1 does not
hold, the collector raises rather than report "no trucks" while one sits
on a later page; the fix is a year-filtered URL (second probe round).

The Toyota marque page (/buy/toyota) was also probed and is not polled:
7,424 adverts, 16 a page, mostly GR Yaris.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.pistonheads import HEADERS, _NEXT_RE

SOURCE = "pistonheads"
URL = "https://www.pistonheads.com/buy/toyota/hilux"
BASE = "https://www.pistonheads.com"


def _era_facet_count(apollo: dict) -> int | None:
    """Adverts dated 1978-1984 per the search's Year facet, or None if the
    page carries no Year facet."""
    root = apollo.get("ROOT_QUERY") or {}
    for key, val in root.items():
        if not key.startswith("advertSearch") or not isinstance(val, dict):
            continue
        for facet in val.get("searchFacets") or []:
            if facet.get("name") != "Year":
                continue
            return sum(v.get("value") or 0 for v in facet.get("values") or []
                       if str(v.get("key", "")).isdigit()
                       and hilux.YEAR_MIN <= int(v["key"]) <= hilux.YEAR_SLOP)
    return None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = (data.get("props", {}).get("pageProps", {}) or {}).get("__APOLLO_STATE__") or {}
    adverts = [v for k, v in apollo.items() if k.startswith("Advert:")]
    if not adverts and "hilux" not in html.lower():
        raise ValueError("no adverts and page does not look like the Hilux search")

    era_on_page = 0
    records = []
    for ad in adverts:
        ad_id = str(ad.get("id") or "")
        if not ad_id:
            continue
        headline = ad.get("headline") or ""
        desc = ad.get("shortDescription") or ""
        spec = ad.get("specificationData") or {}
        year = ad.get("year") if isinstance(ad.get("year"), int) else None
        if year is not None and hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            era_on_page += 1
        # Structured fuel as text, for classify()'s diesel/petrol rules.
        fuel = f" fuel: {spec['fuelType']}" if spec.get("fuelType") else ""
        ident = hilux.classify(headline, desc + fuel, year=year, require_name=False)
        if ident is None:
            continue

        price = ad.get("price")
        amount = float(price) if isinstance(price, (int, float)) else None
        currency = ad.get("currencyCode") or "GBP"
        images = [u for u in (ad.get("fullSizeImageUrls") or [])[:1] if u]
        text = f"{headline} {desc}"

        records.append({
            "id": f"pistonheads:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(ad.get("url") or f"{BASE}/buy/listing/{ad_id}"),
            "title": headline,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": "GB",
            "region": None,
            "drive_side": normalize.infer_drive_side("GB", text),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, currency, fx_day),
            "images": images,
            "status": "active",
        })

    era_total = _era_facet_count(apollo)
    if era_total and era_total > era_on_page:
        raise ValueError(
            f"Year facet counts {era_total} Hilux advert(s) from 1978-1984 but page 1 "
            f"holds {era_on_page}: a 3rd-gen truck is listed beyond the polled page")
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
