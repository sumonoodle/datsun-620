"""Collector: Carsensor (Recruit), Japan's biggest domestic used-car site.

The freeword search for ダットサントラック is server-rendered "cassette"
cards and reachable from GitHub runners (2026-07-17 probe). Like Goo-net
Exchange, most inventory is D21/D22-era (the Datsun Truck name survived to
2002 in Japan), so a record must match the King Cab filter AND a 620-era
registration year. Prices are quoted in 万円 (units of ¥10,000).

Fetch and parse are split so tests run the parser against a saved fixture.
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

SOURCE = "carsensor"
BASE = "https://www.carsensor.net"
QUERY = "ダットサントラック"
URL = f"{BASE}/usedcar/freeword/{quote(QUERY)}/index.html"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.8",
}

_ID_RE = re.compile(r"/usedcar/detail/([A-Z]{2}\d+)/")
_MAN_YEN_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*万円")


def _price_yen(card) -> float | None:
    # 支払総額 (drive-away total) is what Japanese sites lead with; fall back
    # to the base vehicle price. 応談 (negotiable) has no number at all.
    for sel in (".totalPrice__content", ".basePrice__content", ".basePrice__price"):
        el = card.select_one(sel)
        if el:
            m = _MAN_YEN_RE.search("".join(el.get_text(strip=True).split()))
            if m:
                return float(m.group(1).replace(",", "")) * 10_000
    return None


def _reg_year(card) -> int | None:
    # specList leads with 年式 (model year): "2001 (H13)" or "1978 (S53)".
    spec = card.select_one(".specList")
    if spec:
        m = re.search(r"年式\s*(19\d{2}|20\d{2})", spec.get_text(" ", strip=True))
        if m:
            return int(m.group(1))
    return None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = [d for d in soup.find_all("div", class_=True) if "cassette" in d.get("class", [])]
    if not cards and soup.select_one("div.cassetteMain") is None:
        # ダットサントラック reliably returns D21/D22 hits, so a card-less page
        # means the layout changed or we were blocked, not an empty market.
        raise ValueError("zero cassette cards parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        if listing_id in seen:
            continue
        seen.add(listing_id)

        title_el = card.select_one("h3.cassetteMain__title")
        title = " ".join(title_el.get_text(" ", strip=True).split()) if title_el else ""
        year = _reg_year(card)

        # All 620 variants tracked; kc recorded for highlighting, not gating.
        kc = king_cab.check(title)
        if year is None or not 1971 <= year <= 1980:
            continue  # 620 era only; D21/D22 trucks otherwise leak in

        img = card.find("img")
        image = (img.get("data-src") or img.get("src") or "") if img else ""
        if image.startswith("//"):
            image = "https:" + image
        area_el = card.select_one(".cassetteSub__area")

        records.append({
            "id": f"carsensor:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(f"{BASE}/usedcar/detail/{listing_id}/index.html"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": year,
            "country": "JP",
            "region": area_el.get_text(" ", strip=True) if area_el else None,
            "drive_side": normalize.infer_drive_side("JP", title),
            "king_cab": kc,
            "price": normalize.make_price(_price_yen(card), "JPY", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
