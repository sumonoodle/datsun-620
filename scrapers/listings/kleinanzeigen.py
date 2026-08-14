"""Collector: Kleinanzeigen.de (ex-eBay Kleinanzeigen), Datsun pickups in
the cars category.

Germany's dominant classifieds; research found real 620s passing through
(about 1-3 a year) amid Hot Wheels noise, which the cars-category URL
(k0c216) already strips. Cards are server-rendered article.aditem
elements with a stable data-adid, title, EUR price ("12.000 € VB" — VB =
negotiable), postcode+town and date. Kleinanzeigen sits behind Akamai;
the fetch worked from runners on probe day, and if that changes the
degradable pattern reports it and the site moves to the alert route
(it has Suchauftrag email alerts).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "kleinanzeigen"
BASE = "https://www.kleinanzeigen.de"
URL = f"{BASE}/s-autos/datsun-pickup/k0c216"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "de,en;q=0.8",
}

_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_OTHER_GEN_RE = re.compile(r"(?<!\d)(?:520|521|720)(?!\d)|D2[12]|Y720", re.I)
_EUR_RE = re.compile(r"([\d.]+)\s*€")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    ads = soup.find_all("article", class_=re.compile(r"\baditem\b"))
    if not ads and "datsun" not in html.lower():
        raise ValueError("no ad items and page does not look like the search (blocked?)")

    records = []
    seen: set[str] = set()
    for ad in ads:
        ad_id = ad.get("data-adid") or ""
        title_el = ad.select_one(".aditem-main--middle h2 a") or ad.find("h2")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        desc_el = ad.select_one(".aditem-main--middle p")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        text = f"{title} {desc}"
        if not ad_id or ad_id in seen:
            continue
        # The category page carries every Datsun pickup generation; only
        # 620-era trucks belong (the Y720 in the live feed is the pinned
        # exclusion case).
        if not _620_RE.search(text):
            continue
        if _OTHER_GEN_RE.search(text):
            continue
        seen.add(ad_id)

        card_text = ad.get_text(" ", strip=True)
        # German thousands dot: "12.000 €" -> 12000
        pm = _EUR_RE.search(card_text)
        amount = float(pm.group(1).replace(".", "")) if pm else None
        loc_el = ad.select_one(".aditem-main--top--left")
        region = loc_el.get_text(" ", strip=True) if loc_el else None
        href = ad.get("data-href") or (title_el.get("href") if title_el else "")
        img = ad.find("img")
        image = img.get("src") if img else None

        records.append({
            "id": f"kleinanzeigen:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(BASE + href if href.startswith("/") else href),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": normalize.extract_year(text),
            "country": "DE",
            "region": region,
            "drive_side": normalize.infer_drive_side("DE", text),
            "king_cab": king_cab.check(title, desc),
            "price": normalize.make_price(amount, "EUR", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
