"""Hilux collector: Kleinanzeigen.de, keyword "hilux" in the cars category.

Same redesigned results page as the 620 collector (listings/kleinanzeigen.py,
whose card, ld+json, price, EZ and place helpers are reused; read its
docstring for why nothing here selects on CSS classes). The EZ
(first-registration) year is passed to classify() as the structured year.

Differences from the Datsun search:
- Size. "hilux" in c216 was 140 cars on 2026-09-24 (the whole Datsun
  marque is ~28), 25 a page, every car on page 1 registered 1989 or
  later. So up to MAX_PAGES pages are read, bounded by the
  heading's own count. A year-filtered URL would make this one request;
  it is waiting on a second probe round.
- Want-ads. Five of the 25 ads on the probe page were buyers, not
  sellers ("Suche einen Toyota Hilux Pick up", "Suche Alte Vw Taro oder
  Toyota Hilux", "✅ Suche Kaufe ... Mazda"), and a Suche ad carries an EZ
  year like any other (EZ 04/1994 on "Suche Alte Vw Taro"). A title that opens with "Suche" is a buyer.

robots.txt: same paths as the 620 collector (checked 2026-09-19).
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.kleinanzeigen import (BASE, HEADERS, PER_PAGE, _EUR_RE, _EZ_RE, _PLACE_RE,
                                    _image_key, _ld_text, _result_count, _title_from_href)

SOURCE = "kleinanzeigen"
SEARCH = "/s-autos/hilux/k0c216"
# Same two pagination shapes as the 620 collector, tried in the same order.
PAGE_SEARCH = ["/s-autos/seite:{page}/hilux/k0c216",
               "/s-autos/hilux/k0c216/seite:{page}"]
MAX_PAGES = 6  # 140 results at 25/page on 2026-09-24; the cap stops a runaway
_WANTED_RE = re.compile(r"^\W*suche\b", re.I)


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article[data-adid]")
    claimed = _result_count(soup)
    if not cards and claimed:
        raise ValueError(
            f"heading claims {claimed} result(s) but no article[data-adid] "
            f"parsed — card markup changed again?")

    ld = _ld_text(soup)
    records = []
    seen: set[str] = set()
    for card in cards:
        ad_id = card.get("data-adid") or ""
        if not ad_id or ad_id in seen:
            continue
        href = card.get("data-href") or ""
        img = card.find("img")
        image = img.get("src") if img else None
        title, desc = ld.get(_image_key(image or ""), ("", ""))
        if not title:
            title = _title_from_href(href)
        if _WANTED_RE.search(title):
            continue
        card_text = card.get_text(" ", strip=True)
        ez = _EZ_RE.search(card_text)
        ident = hilux.classify(title, desc, year=int(ez.group(2)) if ez else None)
        if ident is None:
            continue
        seen.add(ad_id)

        pm = _EUR_RE.search(card_text)
        amount = float(pm.group(1).replace(".", "")) if pm else None
        place = _PLACE_RE.search(card_text)
        region = place.group(1).strip() if place else None
        text = f"{title} {desc}"

        records.append({
            "id": f"kleinanzeigen:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(BASE + href if href.startswith("/") else href),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": "DE",
            "region": region,
            "drive_side": normalize.infer_drive_side("DE", text),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "EUR", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def _fetch_page(client: httpx.Client, page: int) -> str | None:
    """One results page, or None if this page number cannot be reached
    (a wrong pagination shape redirect-loops, so a guess is never fatal)."""
    if page == 1:
        resp = client.get(BASE + SEARCH)
        resp.raise_for_status()
        return resp.text
    for shape in PAGE_SEARCH:
        try:
            resp = client.get(BASE + shape.format(page=page))
            resp.raise_for_status()
        except Exception:
            continue
        if BeautifulSoup(resp.text, "html.parser").select("article[data-adid]"):
            return resp.text
    return None


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    scanned = 0
    pages = 1
    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS,
                      max_redirects=5) as client:
        page = 1
        while page <= pages:
            try:
                html = _fetch_page(client, page)
            except Exception:
                if page == 1:
                    raise  # page 1 failing IS the source failing
                break
            if html is None:
                print(f"kleinanzeigen (hilux): page {page} unreachable, "
                      f"continuing with {len(records)} record(s)")
                break
            soup = BeautifulSoup(html, "html.parser")
            if page == 1:
                claimed = _result_count(soup) or 0
                pages = min(max(1, math.ceil(claimed / PER_PAGE)), MAX_PAGES)
                if claimed > MAX_PAGES * PER_PAGE:
                    print(f"kleinanzeigen (hilux): {claimed} results, reading the "
                          f"newest {MAX_PAGES * PER_PAGE}")
            for rec in parse_page(html, fx_day):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    records.append(rec)
            cards = len(soup.select("article[data-adid]"))
            scanned += cards
            if cards < PER_PAGE:
                break
            page += 1
    print(f"kleinanzeigen (hilux): scanned {scanned} card(s), "
          f"kept {len(records)} 3rd-gen Hilux")
    return records
