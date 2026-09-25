"""Hilux collector: PistonHeads (UK), the Hilux search capped at 1984.

Same Next.js/Apollo cache as the 620 collector (listings/pistonheads.py):
Advert:<id> entities with headline, native GBP price, year and a
specificationData block. The search is scoped to the Hilux model (M=586)
server-side, so titles need not name it (require_name=False).

Why this URL (2026-09-24 probes):
- /buy/toyota/hilux shows 16 of 293 adverts in PistonHeads' promotion
  order, so a 1980 truck could sit on page 12. Its Year facet showed the
  oldest Hilux was a 1992: no 3rd-gen listed that day.
- /buy/toyota/hilux?yearTo=1984 came back byte-identical: ignored.
- The legacy /classifieds?...&M=586&YearTo=1984 redirects to the URL used
  here, whose cache entry is searchPage({... "makeModelIds": ["586"],
  "yearMax": 1984}) with total 0, agreeing with the facet. The same form
  without a model returned 1,217 adverts, none newer than 1978 on page 1
  (Dinos, Bentleys, a 930 Turbo), so the year cap is really applied.

So every 1978-1984 Hilux in the UK index fits on page 1, and the guards
are about that promise: the searchPage entry must be there with yearMax
applied (else the filter was dropped and we would be reading the 293
modern trucks), and its total must match the adverts on the page (else a
truck sits on page 2, or the cards moved).
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
BASE = "https://www.pistonheads.com"
URL = f"{BASE}/buy/search?M=586&year=1900&year=1984"
YEAR_MAX = 1984


def _search_entry(apollo: dict) -> tuple[dict, dict]:
    """(query input, result) of the page's searchPage cache entry."""
    root = apollo.get("ROOT_QUERY") or {}
    for key, val in root.items():
        if key.startswith("searchPage(") and isinstance(val, dict):
            try:
                args = json.loads(key[len("searchPage("):-1])
            except ValueError:
                args = {}
            return args.get("input") or {}, val
    raise ValueError("searchPage entry missing (page layout changed or blocked?)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = (data.get("props", {}).get("pageProps", {}) or {}).get("__APOLLO_STATE__") or {}
    query, result = _search_entry(apollo)
    if query.get("yearMax") != YEAR_MAX:
        raise ValueError(f"search ran without the {YEAR_MAX} year cap ({query.get('yearMax')!r})")

    refs = [r.get("__ref") for r in (result.get("adverts") or []) if isinstance(r, dict)]
    adverts = [apollo[r] for r in refs if r in apollo]
    total = result.get("total")
    if isinstance(total, int) and total != len(adverts):
        raise ValueError(
            f"search counts {total} Hilux advert(s) to {YEAR_MAX} but {len(adverts)} "
            f"parsed: a truck is beyond page 1, or the advert cache moved")

    records = []
    for ad in adverts:
        ad_id = str(ad.get("id") or "")
        if not ad_id:
            continue
        headline = ad.get("headline") or ""
        desc = ad.get("shortDescription") or ""
        spec = ad.get("specificationData") or {}
        year = ad.get("year") if isinstance(ad.get("year"), int) else None
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
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
