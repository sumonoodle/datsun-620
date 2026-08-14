"""Collector: Ratsun.net classifieds, the Datsun truck community's own market.

The Datsun Vehicles category is an Invision classifieds app: each item is
an /classifieds/item/<id>-<slug>/ link with title, a USD price and a
FOR SALE / COMPLETED state on the card (COMPLETED = sold/closed).
Research found the highest 620 density of any source here ($800 rollers
to $13k trucks). Titles are loose forum titles, so the 620 regex plus the
cross-generation rule do the filtering — "1971 521, sale or trade for 620
ext cab" is a 521 and must not leak in.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "ratsun"
URL = "https://ratsun.net/classifieds/category/5-datsun-vehicles/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

_ITEM_RE = re.compile(r"/classifieds/item/(\d+)-[^/'\"]+/?")
_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_OTHER_GEN_RE = re.compile(r"(?<!\d)(?:520|521|720)(?!\d)|D2[12]", re.I)
_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = [a for a in soup.find_all("a", href=_ITEM_RE) if a.get_text(strip=True)]
    if not anchors:
        raise ValueError("zero classified items parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for a in anchors:
        item_id = _ITEM_RE.search(a["href"]).group(1)
        title = a.get_text(" ", strip=True)
        if item_id in seen or len(title) < 8:
            continue
        if not _620_RE.search(title):
            continue
        if _OTHER_GEN_RE.search(title):
            continue
        seen.add(item_id)

        card = a
        for _ in range(5):
            parent = card.find_parent()
            if parent is None:
                break
            card = parent
            if "$" in card.get_text() or "FOR SALE" in card.get_text():
                break
        card_text = card.get_text(" ", strip=True)
        pm = _PRICE_RE.search(card_text)
        amount = float(pm.group(1).replace(",", "")) if pm else None
        sold = "COMPLETED" in card_text
        img = card.find("img")
        image = (img.get("src") or img.get("data-src")) if img else None

        url = a["href"]
        if url.startswith("/"):
            url = "https://ratsun.net" + url

        records.append({
            "id": f"ratsun:{item_id}",
            "source": SOURCE,
            "source_listing_id": item_id,
            "url": normalize.safe_url(url),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": normalize.extract_year(title),
            "country": "US",  # Ratsun is overwhelmingly US-based; listings state location in-thread
            "region": None,
            "drive_side": normalize.infer_drive_side("US", title),
            "king_cab": king_cab.check(title),
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [image] if image else [],
            "status": "sold" if sold else "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
