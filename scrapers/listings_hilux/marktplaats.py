"""Hilux collector: Marktplaats (NL), "toyota hilux" inside the Auto's category.

The page is Next.js; __NEXT_DATA__ carries searchRequestAndResponse with
the listings (itemId, title, description, priceInfo in cents, location,
structured attributes constructionYear / fuel, vipUrl, pictures), the
search's totalResultCount and the request it answered (category, query,
pagination offset).

Why the category URL. The first probe, /q/toyota+hilux/, returned 973
results that were mostly parts, bullbars, brochures and model cars, 30 a
page. Round 3 (2026-09-24) fetched the category-scoped search
/l/auto-s/q/toyota+hilux/: 72 results, all vehicles (Toyota and
Bestelauto's categories), and page 1 held a REAL 1981 truck: "Toyota 1981"
(m2438531579), a US-import petrol Hilux in Amsterdam whose title never
says Hilux; the description does ("toyota hilux op benzine") and the
structured year is 1981. The other two round-3 scopes were weaker:
/l/auto-s/toyota/q/hilux/ (39 results) misses Bestelauto's, where that
1981 truck is filed, and /l/auto-s/oldtimers/q/toyota/ (44) is every old
Toyota (Corollas, Land Cruisers) and adds nothing a "hilux" text search
does not already catch.

72 results is three pages. Page 1 is the verified URL; later pages use
the site's /p/<n>/ path shape (seen as /q/toyota+hilux/p/2/ on the first
probe) and are only trusted when the payload echoes the matching
pagination offset, so an ignored page parameter cannot duplicate page 1
silently. A failed later page is logged, not fatal.

Guard: __NEXT_DATA__ missing raises; totalResultCount > 0 with no listing
raises; zero results returns nothing.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "marktplaats"
BASE = "https://www.marktplaats.nl"
URL = f"{BASE}/l/auto-s/q/toyota+hilux/"
PAGE_SIZE = 30
MAX_PAGES = 5
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}

_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
# Whole vehicles only. The Auto's category holds cars and vans; want-ads
# ("Gevraagd ...") and buy-up services live there too and are dropped by
# classify() (no year) or by the want-ad words below.
_VEHICLE_PATH = "/v/auto-s/"
_WANTED_RE = re.compile(r"\bgevraagd\b|\bgezocht\b|\binkoop\b", re.I)


def page_url(page: int) -> str:
    return URL if page == 1 else f"{URL}p/{page}/"


def _search(html: str) -> dict:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    sr = ((data.get("props") or {}).get("pageProps") or {}).get("searchRequestAndResponse")
    if not isinstance(sr, dict):
        raise ValueError("searchRequestAndResponse missing (payload moved?)")
    return sr


def page_offset(html: str) -> int | None:
    pag = ((_search(html).get("searchRequest") or {}).get("pagination") or {})
    return pag.get("offset") if isinstance(pag.get("offset"), int) else None


def total_count(html: str) -> int | None:
    t = _search(html).get("totalResultCount")
    return t if isinstance(t, int) else None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    sr = _search(html)
    listings = sr.get("listings") or []
    total = sr.get("totalResultCount")
    if not listings:
        if total:
            raise ValueError(f"search reports {total} results but no listing was parsed")
        return []

    records = []
    for item in listings:
        item_id = str(item.get("itemId") or "")
        vip = item.get("vipUrl") or ""
        if not item_id or not vip.startswith(_VEHICLE_PATH):
            continue
        title = (item.get("title") or "").strip()
        desc = (item.get("categorySpecificDescription") or item.get("description") or "").strip()
        if _WANTED_RE.search(title):
            continue
        attrs = {a.get("key"): str(a.get("value") or "") for a in item.get("attributes") or []}
        ext = {a.get("key"): str(a.get("value") or "") for a in item.get("extendedAttributes") or []}
        brand = ext.get("brand", "")
        if brand and brand.lower() != "toyota":
            continue
        year_raw = attrs.get("constructionYear", "")
        year = int(year_raw) if year_raw.isdigit() else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        # Fuel ("Benzine"/"Diesel") and displacement ride along: a title like
        # "Toyota 1981" is only identified by its description and attributes.
        detail = " ".join(x for x in [desc, attrs.get("fuel", ""),
                                      ext.get("engineDisplacement", "")] if x)
        ident = hilux.classify(title, detail, year=year, body_style=attrs.get("body") or None)
        if ident is None:
            continue

        price = item.get("priceInfo") or {}
        cents = price.get("priceCents")
        # Bid-only ads ("FAST_BID"/"SEE_DESCRIPTION") carry 0 cents: no price.
        amount = round(cents / 100, 2) if isinstance(cents, (int, float)) and cents > 0 else None
        loc = item.get("location") or {}
        country = normalize.to_country_code(loc.get("countryAbbreviation") or "NL")
        pics = item.get("pictures") or []
        image = (pics[0].get("largeUrl") or pics[0].get("mediumUrl")) if pics else None

        records.append({
            "id": f"marktplaats:{item_id}",
            "source": SOURCE,
            "source_listing_id": item_id,
            "url": normalize.safe_url(f"{BASE}{vip}"),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": country,
            "region": loc.get("cityName") or None,
            "drive_side": normalize.infer_drive_side(country, f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "EUR", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()

    def add(batch):
        for rec in batch:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                records.append(rec)

    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(page_url(1))
        resp.raise_for_status()
        first = resp.text
        add(parse_page(first, fx_day))
        pages = min(MAX_PAGES, math.ceil((total_count(first) or 0) / PAGE_SIZE))
        for page in range(2, pages + 1):
            try:
                resp = client.get(page_url(page))
                resp.raise_for_status()
                if page_offset(resp.text) != (page - 1) * PAGE_SIZE:
                    raise ValueError("page parameter not applied (offset echo mismatch)")
                add(parse_page(resp.text, fx_day))
            except Exception as exc:
                print(f"marktplaats (hilux): page {page} skipped ({exc})")
                break
    return records
