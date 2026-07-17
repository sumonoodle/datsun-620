"""Collector: 中古車EX (kuruma-ex.jp), Datsun model search.

kuruma-ex aggregates the Carsensor and Goo dealer feeds, so it covers
Goo's DOMESTIC inventory that our Goo-net Exchange collector misses — and
it has hosted a real 620 (a 1974 SR20-swapped reimport). The Datsun model
search (maker NI, shashu S061) is server-rendered div.car-item cards with
支払総額/本体価格 in 万円 and a 年式 year. The feed includes D21-era
"Datsun" trucks (a SEV6 キングキャブ Hardbody sat in it on fetch day), so
the era gate is required exactly as on Carsensor.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "kuruma_ex"
BASE = "https://kuruma-ex.jp"
URL = f"{BASE}/usedcar/search/result/maker/NI/shashu/S061"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.8",
}

_ID_RE = re.compile(r"/usedcar/detail/(cc[A-Z]{2}\d+)")
_YEAR_RE = re.compile(r"年式\s*(19\d{2}|20\d{2})年")
_MAN_YEN_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*万円")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.car-item")
    if not cards:
        # The Datsun model feed always has D21/D22-era stock, so an empty
        # page means the layout moved, not an empty market.
        raise ValueError("zero car-item cards parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        if listing_id in seen:
            continue
        text = card.get_text(" ", strip=True)
        # Card text leads with maker + grade line, e.g.
        # "日産 ダットサンピックアップトラック MT 支払総額 130.5万円 …"
        title = " ".join(text.split("支払総額")[0].split())[:120]

        kc = king_cab.check(title, text[:300])
        if not kc["matched"]:
            continue
        ym = _YEAR_RE.search(text)
        year = int(ym.group(1)) if ym else None
        if year is None or not 1971 <= year <= 1980:
            continue  # D21/D22 King Cab grades otherwise leak in
        seen.add(listing_id)

        pm = _MAN_YEN_RE.search(text)
        amount = float(pm.group(1).replace(",", "")) * 10_000 if pm else None
        img = card.find("img")
        image = (img.get("data-src") or img.get("src") or "") if img else ""
        if image.startswith("//"):
            image = "https:" + image

        records.append({
            "id": f"kuruma_ex:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(BASE + a["href"] if a["href"].startswith("/") else a["href"]),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": year,
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", text),
            "king_cab": kc,
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
