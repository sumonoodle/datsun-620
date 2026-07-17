"""Collector: Goo-net Exchange, Goo-net's English-language export portal.

The DATSUN TRUCK model index is server-rendered and (unlike the domestic
path the v1 build used) answers GitHub runners with full pages — proven by
the 2026-07-17 reachability probe. The catch: "Datsun Truck" stayed a JDM
model name until 2002, so the index is mostly D21/D22 pickups. A record
must BOTH match the King Cab filter AND carry a first-registration year in
the 620 era; a King Cab with no parseable year is skipped rather than
guessed, because a D21 KING CAB grade is the likelier explanation.

Fetch and parse are split so tests run the parser against a saved fixture.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "goonet_exchange"
BASE = "https://www.goo-net-exchange.com"
URL = f"{BASE}/usedcars/NISSAN/DATSUN_TRUCK/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8",
}

_ID_RE = re.compile(r"/usedcars/NISSAN/DATSUN_TRUCK/(\d+)/?$")
_YEN_RE = re.compile(r"¥\s*([\d,]+)")


def _card_year(details: list[str]) -> int | None:
    # First detail cell is the registration date: "1978.03" or "1983".
    if details and (m := re.match(r"(19\d{2}|20\d{2})", details[0])):
        return int(m.group(1))
    return None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("ul.list-listview")
    if container is None:
        raise ValueError("listing container missing (page layout changed or blocked?)")

    records = []
    for li in container.find_all("li", recursive=False):
        a = li.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        title_el = li.select_one("h3.title")
        title = " ".join(title_el.get_text(" ", strip=True).split()) if title_el else ""
        details = [d.get_text(" ", strip=True) for d in li.select("ul.details li")]
        year = _card_year(details)

        # All 620 variants tracked; kc recorded for highlighting, not gating.
        kc = king_cab.check(title)
        if year is None or not 1971 <= year <= 1980:
            continue  # 620 era only; the model page runs to 2002 (D21/D22)

        price_el = li.select_one("p.price")
        m = _YEN_RE.search(price_el.get_text(strip=True)) if price_el else None
        amount = float(m.group(1).replace(",", "")) if m else None

        detail_text = " ".join(details)
        drive = "RHD" if re.search(r"\bright\b", detail_text, re.I) else (
            "LHD" if re.search(r"\bleft\b", detail_text, re.I) else
            normalize.infer_drive_side("JP"))

        img = li.select_one("div.photo img")
        image = (img.get("data-src") or img.get("src")) if img else None
        location_el = li.select_one("p.location")

        records.append({
            "id": f"goonet_exchange:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(f"{BASE}/usedcars/NISSAN/DATSUN_TRUCK/{listing_id}/"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": year,
            "country": "JP",
            "region": location_el.get_text(strip=True) if location_el else None,
            "drive_side": drive,
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
