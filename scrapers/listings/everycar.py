"""Collector: EVERY Co. (everycar.jp), Japan export portal, Datsun Truck feed.

Deferred in the July deep dive as thin, promoted in September when the
owner asked for more Japan coverage. The model-filtered stock query pads
with unrelated Nissans (Civilians, Caravans) when no Datsun Truck is in
stock, so the structural filter is the detail URL itself:
/nissan/<model-slug>/<year>/<id>/ — the slug must be a Datsun model and
the year must sit in the 620 era (everycar has sold 1963-1994 Datsuns, so
era gating matters). Cards are li.listItem with a stock number, spec
table and a USD FOB price.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_OTHER_GEN

SOURCE = "everycar"
URL = "https://www.everycar.jp/used-cars.php?make=nissan&model=datsun-truck"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

# /nissan/datsun-truck/1978/7912345/ — model slug and year are in the path.
_DETAIL_RE = re.compile(
    r"everycar\.jp/nissan/(datsun[a-z0-9-]*)/((?:19|20)\d{2})/(\d+)/")
_USD_RE = re.compile(r"\$\s*([\d,]+)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.listItem")
    if not cards and "datsun" not in html.lower():
        raise ValueError("no stock cards and page does not look like the search (blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_DETAIL_RE)
        if a is None:
            continue  # padding stock (Civilians, Caravans) has non-Datsun slugs
        slug, year_s, listing_id = _DETAIL_RE.search(a["href"]).groups()
        year = int(year_s)
        if listing_id in seen:
            continue
        if not 1971 <= year <= 1980:
            continue  # everycar sells 1980s-90s Datsun-badged trucks too
        text = card.get_text(" ", strip=True)
        title = " ".join(text.split("Stock NO")[0].split())
        # Cards lead with the stock number before the model name.
        title = re.sub(r"^[0-9][A-Z0-9]{6,}\s+", "", title)[:120] or f"Datsun Truck {year}"
        if RE_OTHER_GEN.search(title):
            continue
        seen.add(listing_id)

        pm = _USD_RE.search(text)
        amount = float(pm.group(1).replace(",", "")) if pm else None
        img = card.find("img")
        image = (img.get("data-src") or img.get("src")) if img else None
        if image and image.startswith("//"):
            image = "https:" + image

        records.append({
            "id": f"everycar:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(a["href"]),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": year,
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", text),
            "king_cab": king_cab.check(title, text[:300]),
            "price": normalize.make_price(amount, "USD", fx_day),  # FOB prices are USD
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
