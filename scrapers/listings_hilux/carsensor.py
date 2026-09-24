"""Hilux collector: Carsensor (Recruit), freeword ハイラックス with a year cap.

Same server-rendered "cassette" cards as the Datsun collector
(listings/carsensor.py), so its card helpers are shared. The query is not:
the uncapped freeword search the 2026-09-24 runner probe fetched held 37
pages of 30 cards, and page 1 was 2019-2026 Z / GR SPORT diesels and
2003-2007 Hilux Surfs. A 1980 truck would never surface on page 1.

So the search is capped with YMAX, the same parameter the page's own
panelForm submits (its 年式 dropdown bottoms out at 1989, hence 1989
rather than 1984; classify() and the era gate below do the rest). The
cap was not in the first probe round, so it is guarded: a card newer than
the cap means Carsensor ignored the parameter, and that raises instead of
quietly returning page 1 of the modern market.

Freeword rather than the ハイラックス model page (bTO/s112, the page's
canonical): a 1978-83 truck can be filed under a different Carsensor model
code by a dealer, and the freeword hits it either way.

Prices are 万円 (units of ¥10,000). Fetch and parse are split so tests run
the parser against a saved fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.carsensor import BASE, HEADERS, _ID_RE, _price_yen, _reg_year

SOURCE = "carsensor"
QUERY = "ハイラックス"
# Lowest value Carsensor's own 年式 (YMAX) dropdown offers.
YEAR_CAP = 1989
URL = f"{BASE}/usedcar/freeword/{quote(QUERY)}/index.html?YMAX={YEAR_CAP}"


def parse_page(html: str, fx_day: dict, year_cap: int | None = YEAR_CAP) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = [d for d in soup.find_all("div", class_=True) if "cassette" in d.get("class", [])]
    if not cards and soup.select_one("div.cassetteMain") is None:
        # With a year cap an empty result is an ordinary day (the 3rd gen is
        # rare), but only if this is still the search page: its filter form
        # is the proof. Anything else is a layout change or a block.
        if soup.select_one("form#panelForm") is None:
            raise ValueError("zero cassette cards and no search form (layout changed or blocked?)")
        return []

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
        if year_cap is not None and year is not None and year > year_cap:
            raise ValueError(f"card year {year} above YMAX={year_cap}: year filter ignored")
        # 年式 is structured and reliable here; outside the window is out,
        # whatever the title says (classify() alone would fall back to text).
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        spec = card.select_one(".specList")
        body = card.select_one(".carBodyInfoList")
        desc = " ".join(el.get_text(" ", strip=True) for el in (body, spec) if el)
        ident = hilux.classify(title, desc, year=year)
        if ident is None:
            continue

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
            "year": ident["year"],
            "country": "JP",
            "region": area_el.get_text(" ", strip=True) if area_el else None,
            "drive_side": normalize.infer_drive_side("JP", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(_price_yen(card), "JPY", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    # One page: 1989-and-older Hiluxes of every generation are expected to
    # fit in Carsensor's 30-card page. If that stops being true, say so in
    # the run log rather than follow a next link that may drop the cap.
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    if '<link rel="next"' in resp.text:
        print("carsensor (hilux): capped search has a page 2; only page 1 read")
    return parse_page(resp.text, fx_day)
