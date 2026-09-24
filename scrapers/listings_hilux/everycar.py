"""Hilux collector: EVERY Co. (everycar.jp), Toyota Hilux feed.

Same li.listItem cards and same structural filter as the Datsun collector
(listings/everycar.py): the detail URL itself is /toyota/<model>/<year>/<id>/,
so model and registration year are read from the path, not the text.

Same lesson too: the model slug is read from the make page's live
<select name="model"> (which lists in-stock models only), never assumed.
everycar builds facets from inventory, and a facet with no stock answers
a real "Page Not Found", so a missing hilux slug is an empty market, not a
failure. On the 2026-09-24 probe the Toyota make page offered 56 models
including "hilux" (30 in stock, every one a GUN125 diesel on page 1).

Each card's spec table carries Model Code (e.g. 3DF-GUN125, and for a
3rd-gen truck an RN3x/RN4x code) and Fuel, and both go to classify() as
description, so a diesel or a wrong-generation code rejects even when the
title is just "TOYOTA HILUX". The model page is read in full (pages of 25,
"?page=N"), up to MAX_PAGES.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.everycar import BASE, HEADERS, _USD_RE, model_slugs

SOURCE = "everycar"
MAKE_URL = f"{BASE}/used-cars?make=toyota"
MAX_PAGES = 5

_DETAIL_RE = re.compile(r"everycar\.jp/toyota/(hilux[a-z0-9-]*)/((?:19|20)\d{2})/(\d+)/")
# Hilux-family slugs, minus the Surf (an SUV; a separate model everywhere).
_HILUX_SLUG_RE = re.compile(r"^hilux(?!-surf)")


def _spec(card) -> dict[str, str]:
    """Spec table as {label: value}: the ul.car_models rows alternate
    label/value cells (Stock NO, Model Code, Reg Year/Month, Fuel...)."""
    cells = [li.get_text(" ", strip=True) for li in card.select("ul.car_models li")]
    return dict(zip(cells[0::2], cells[1::2]))


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.listItem")
    if not cards and "hilux" not in html.lower():
        raise ValueError("no stock cards and page does not look like the search (blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_DETAIL_RE)
        if a is None:
            continue  # padding stock from other models
        slug, year_s, listing_id = _DETAIL_RE.search(a["href"]).groups()
        year = int(year_s)
        if listing_id in seen:
            continue
        if not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue  # the path year is structural; modern stock stops here
        name_el = card.select_one("h2.car_company")
        title = " ".join(name_el.get_text(" ", strip=True).split()) if name_el else f"TOYOTA HILUX {year}"
        spec = _spec(card)
        desc = " ".join(f"{k} {v}" for k, v in spec.items()
                        if k in ("Model Code", "Engine CC", "Fuel", "Transmission"))
        ident = hilux.classify(title, desc, year=year, require_name=False)
        if ident is None:
            continue
        seen.add(listing_id)

        text = card.get_text(" ", strip=True)
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
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", text),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "USD", fx_day),  # FOB prices are USD
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        resp = client.get(MAKE_URL)
        resp.raise_for_status()
        offered = model_slugs(resp.text)
        if not offered:
            # The make page always offers models (56 for Toyota on probe
            # day); an empty dropdown is a layout change, not a market.
            raise RuntimeError("make=toyota page offered no model dropdown (layout changed?)")
        slugs = [s for s in offered if _HILUX_SLUG_RE.search(s)]
        if not slugs:
            print(f"everycar (hilux): no Hilux model in stock ({len(offered)} Toyota models offered)")
            return []
        for slug in slugs:
            paged: set[str] = set()
            for page in range(1, MAX_PAGES + 1):
                url = (f"{BASE}/used-cars?make=toyota&model={slug}" if page == 1 else
                       f"{BASE}/used-cars?page={page}&make=toyota&model={slug}")
                resp = client.get(url)
                if page > 1 and resp.status_code == 404:
                    break  # past the last page of an unpaginated facet
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day):
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
                # Stop on a page with no Hilux card not already seen: that
                # covers both an empty past-the-end page and a site that
                # repeats its last page.
                ids = {m[2] for m in _DETAIL_RE.findall(resp.text)}
                if not ids - paged:
                    break
                paged |= ids
    return records
