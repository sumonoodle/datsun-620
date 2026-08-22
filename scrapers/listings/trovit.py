"""Collector: Trovit Cars (US), the datsun-620 aggregator page.

Trovit aggregates other classifieds (dealer sites, Craigslist relays,
ClassicCars networks), so it is a SAFETY NET: 620s whose home site we
don't scrape surface here. Cards are server-rendered div.item elements
with a stable data-id, title, $ price, "ZIP, ST" address and year.
Outbound links are tracking redirects — recorded as-is; the relist
detector pairs duplicates with their home-site records rather than us
trying to resolve redirect targets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "trovit"
URL = "https://cars.trovit.com/used-cars/datsun-620"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_OTHER_GEN_RE = re.compile(r"(?<!\d)(?:520|521|720)(?!\d)|D2[12]", re.I)
_USD_RE = re.compile(r"\$\s*([\d,]+)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div.item.js-item")
    if not items:
        raise ValueError("zero items parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for it in items:
        item_id = it.get("data-id") or ""
        title_el = it.select_one(".item-title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        desc_el = it.select_one(".item-description-text")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        if not item_id or item_id in seen:
            continue
        # The page is 620-scoped, but aggregators drift: hold the line, and
        # in the TITLE — the live page carried a "See Video at" stub card
        # whose only 620 lived in the description.
        if not _620_RE.search(title):
            continue
        if _OTHER_GEN_RE.search(title):
            continue
        seen.add(item_id)

        price_el = it.select_one(".actual-price")
        pm = _USD_RE.search(price_el.get_text(strip=True)) if price_el else None
        amount = float(pm.group(1).replace(",", "")) if pm else None
        addr_el = it.select_one(".item-address")
        region = addr_el.get_text(" ", strip=True) if addr_el else None
        a = it.find("a", href=True)
        img = it.select_one("img.snippet-image")
        image = img.get("src") if img else None
        if image and image.startswith("//"):
            image = "https:" + image

        records.append({
            "id": f"trovit:{item_id}",
            "source": SOURCE,
            "source_listing_id": item_id,
            "url": normalize.safe_url(a["href"] if a else URL),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": normalize.extract_year(f"{title} {desc}"),
            "country": "US",
            "region": region,
            "drive_side": normalize.infer_drive_side("US", f"{title} {desc}"),
            "king_cab": king_cab.check(title, desc),
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
