"""Collector: FLEX (flexnet.co.jp), Japan's strongest classic-620 dealer.

FLEX's kyusha (classic) division has documented 620 stock history (an
L18-swapped 1974, an LHD one-owner truck). The freeword search for
ダットサン is server-rendered: div.usdbox cards with the title in an h3,
a sales blurb, a 年式 (model year) table and a SOLD OUT badge when gone.
Prices are 万円 when shown; many classics are 応談 (negotiable) with no
number. Era + King Cab + 620 filters as with the other Japanese sources.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620, RE_OTHER_GEN

SOURCE = "flex"
URL = "https://www.flexnet.co.jp/search/freeword/" + quote("ダットサン")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.8",
}

_ID_RE = re.compile(r"/detail/[^\"]*-used-(\d+)\.html")
_YEAR_RE = re.compile(r"(19\d{2}|20\d{2})年")
_MAN_YEN_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*万円")
_620_RE = RE_620


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.usdbox")
    if not cards:
        raise ValueError("zero stock cards parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        if listing_id in seen:
            continue
        title_el = card.select_one(".useditem__ttl h3")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        blurb_el = card.select_one(".useditem__ttl p")
        blurb = blurb_el.get_text(" ", strip=True) if blurb_el else ""
        text = f"{title} {blurb}"

        # All 620 variants tracked; kc recorded for highlighting, not gating.
        # A 620 at FLEX may be titled ダットサントラック with no "620", so an
        # era-gated model-name match counts too (the era gate below vetoes
        # the D21/D22 trucks that share the name).
        kc = king_cab.check(title, blurb)
        if not (_620_RE.search(text) or "ダットサントラック" in title):
            continue
        # 年式 strictly from the details table: a blurb like
        # "2020年にフルレストア済!" (restored in 2020) must not read as the
        # model year and silently veto a real 1978 truck (2026-08-22 bug).
        detail = card.select_one(".usd_detailbox")
        detail_text = detail.get_text(" ", strip=True) if detail else ""
        ym = _YEAR_RE.search(detail_text)
        year = int(ym.group(1)) if ym else None
        if year is not None and not 1971 <= year <= 1980:
            continue
        seen.add(listing_id)

        # Price from the card MINUS the blurb, so a restoration spend
        # ("300万円かけてレストア") in the sales pitch can't become the price.
        price_scope = card.get_text(" ", strip=True)
        if blurb:
            price_scope = price_scope.replace(blurb, " ")
        pm = _MAN_YEN_RE.search(price_scope.replace(" ", ""))
        amount = float(pm.group(1).replace(",", "")) * 10_000 if pm else None
        if amount == 0:
            amount = None
        img = card.select_one(".usd_phbox img")
        image = (img.get("src") or img.get("data-src")) if img else None
        sold = "SOLD OUT" in card.get_text()

        records.append({
            "id": f"flex:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            # Detail slugs contain Japanese; live hrefs come percent-encoded
            # but the schema's uri format demands it either way. A relative
            # href would otherwise become an empty url via safe_url.
            "url": normalize.safe_url(quote(
                ("https://www.flexnet.co.jp" + a["href"]) if a["href"].startswith("/") else a["href"],
                safe=":/?&=%")),
            "title": title,
            "title_translated": None,
            "description_snippet": (blurb[:500] or None),
            "year": year,
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", text),
            "king_cab": kc,
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [image] if image else [],
            "status": "sold" if sold else "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
