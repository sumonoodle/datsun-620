"""Collector: Hemmings classifieds (tier 2, degradable).

Hemmings served HTTP 403 to GitHub runners throughout the v1.0 build, so this
source is expected to be blocked some or all of the time. A block raises and
is absorbed by the per-source isolation; the parse contract is pinned by a
fixture test so the collector is ready whenever requests get through.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "hemmings"
URL = "https://www.hemmings.com/classifieds/cars-for-sale/datsun/620"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}

_PRICE_RE = re.compile(r"\$\s?([\d,]+)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/listing/" not in href and "/cars-for-sale/" not in href:
            continue
        # Listing links carry the vehicle title; navigation links don't.
        title = a.get_text(" ", strip=True)
        if not re.search(r"\b620\b", title) or "datsun" not in title.lower():
            continue
        kc = king_cab.check(title)
        if not kc["matched"]:
            continue

        url = href if href.startswith("http") else f"https://www.hemmings.com{href}"
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug in seen:
            continue
        seen.add(slug)

        # Price usually sits in the same card; look at the enclosing block.
        card = a.find_parent(["li", "article", "div"]) or a
        m = _PRICE_RE.search(card.get_text(" ", strip=True))
        amount = float(m.group(1).replace(",", "")) if m else None
        img = card.find("img")

        records.append({
            "id": f"hemmings:{slug}",
            "source": SOURCE,
            "source_listing_id": slug,
            "url": url,
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": normalize.extract_year(title),
            "country": "US",
            "region": None,
            "drive_side": normalize.infer_drive_side("US", title),
            "king_cab": kc,
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [img["src"]] if img and img.get("src", "").startswith("http") else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    if resp.status_code in (403, 429, 503):
        raise RuntimeError(f"HTTP {resp.status_code} (bot protection / blocked)")
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
