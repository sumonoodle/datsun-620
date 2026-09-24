"""Hilux collector: Gumtree South Africa, Toyota > Hilux, petrol, all pages.

South Africa is one of the biggest Hilux markets in the world, and 3rd-gen
petrol bakkies (1.6/1.8/2.0) still trade there as working trucks. The
search page is server-rendered (eBay "Bolt" platform): each result is a
<span class="related-item" data-adid=...> whose data-brevo-* attributes
carry the title, price, currency, link, image, location, status and a
JSON attribute block with CarYear, FuelType and CarBodyType. Those
attributes are what is parsed, not the visible text.

Why the petrol facet. The 2026-09-24 probe of the make/model page
(/s-cars-bakkies/toyota~hilux/v1c9077a2mamop1) held 264 results in 14
pages of 20, newest first, and page 1 was 1999-2018 trucks. The page's
own filter panel counts Petrol 73 / Diesel 191, and its (ROT13-encoded)
filter links give the petrol facet path, toyota~hilux~petrol/
v1c9077a3mamofup1. 73 results is four pages, so every petrol Hilux in the
country is read each day. The year dropdown (1978, 1983 ... options) posts
through a JS form and has no link on the page, so it is not used.

The facet URL is the page's own link but was not itself fetched in the
first probe round; the guard makes a mismatch fail loudly.

Guard: the heading's "(N results)" is compared with the cards parsed on
page 1: results promised but no card read raises; zero results returns
nothing. Later pages stop at the result count, or early on an empty page.
"""

from __future__ import annotations

import html as html_lib
import json
import math
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "gumtree_za"
BASE = "https://www.gumtree.co.za"
PAGE_SIZE = 20
MAX_PAGES = 8  # 73 petrol Hiluxes on probe day = 4 pages; headroom, not a crawl
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-ZA,en;q=0.9",
}

_CARD_RE = re.compile(r'<span class="related-item\b[^"]*"([^>]*)>')
_ATTR_RE = re.compile(r'(data-[\w-]+)="([^"]*)"')
_COUNT_RE = re.compile(r'<span class="ads-count">\s*\(([\d,]+) results?\)')


def page_url(page: int) -> str:
    """Petrol-facet URL for a results page (the site's own pagination
    shape: /page-2/ and a trailing p2 on the id segment)."""
    if page == 1:
        return f"{BASE}/s-cars-bakkies/toyota~hilux~petrol/v1c9077a3mamofup1"
    return f"{BASE}/s-cars-bakkies/toyota~hilux~petrol/page-{page}/v1c9077a3mamofup{page}"


def result_count(html: str) -> int | None:
    m = _COUNT_RE.search(html)
    return int(m.group(1).replace(",", "")) if m else None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    # Only the results block: the page also embeds a featured-ads gallery
    # from unrelated categories (a compressor on the probe page).
    start = html.find('id="srpAds"')
    total = result_count(html)
    if start < 0:
        if total == 0:
            return []
        raise ValueError("srpAds results block missing (page layout changed or blocked?)")
    cards = _CARD_RE.findall(html[start:])
    if not cards:
        if total:
            raise ValueError(f"search reports {total} results but no card was parsed")
        return []

    records = []
    for raw in cards:
        a = {k: html_lib.unescape(v) for k, v in _ATTR_RE.findall(raw)}
        ad_id = a.get("data-adid", "")
        link = a.get("data-brevo-ad-link", "")
        if not ad_id or not link:
            continue
        if a.get("data-brevo-ad-status", "ACTIVE").upper() != "ACTIVE":
            continue
        try:
            attrs = json.loads(a.get("data-brevo-attributes") or "{}")
        except ValueError:
            attrs = {}
        if str(attrs.get("CarMake", "toyota")).lower() != "toyota":
            continue
        year = attrs.get("CarYear") if isinstance(attrs.get("CarYear"), int) else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        title = a.get("data-brevo-ad-title", "").strip()
        fuel = str(attrs.get("FuelType") or "")
        body = str(attrs.get("CarBodyType") or "")
        # The model is structured (CarModel: Hilux), so the title need not
        # name it; bakkie sellers often write just "1981 Toyota 1600".
        named = str(attrs.get("CarModel", "")).lower() == "hilux"
        ident = hilux.classify(title, f"{fuel} {body}".strip(), year=year,
                               require_name=not named, body_style=body or None)
        if ident is None:
            continue

        price = a.get("data-brevo-ad-price", "")
        amount = float(price) if re.fullmatch(r"\d+(?:\.\d+)?", price) else None
        currency = a.get("data-brevo-currency") or "ZAR"
        image = a.get("data-brevo-image-url")

        records.append({
            "id": f"gumtree_za:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(f"{BASE}{link}" if link.startswith("/") else link),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "ZA",
            "region": a.get("data-brevo-location") or None,
            "drive_side": normalize.infer_drive_side("ZA", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, currency, fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(page_url(1))
        resp.raise_for_status()
        first = resp.text
        pages = min(MAX_PAGES, math.ceil((result_count(first) or 0) / PAGE_SIZE) or 1)
        for page in range(1, pages + 1):
            if page > 1:
                resp = client.get(page_url(page))
                resp.raise_for_status()
            html = first if page == 1 else resp.text
            if page > 1 and 'data-adid="' not in html:
                break  # ran past the last page (listings sold since page 1 was read)
            for rec in parse_page(html, fx_day):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    records.append(rec)
    return records
