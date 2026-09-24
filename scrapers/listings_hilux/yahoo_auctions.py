"""Hilux collector: Yahoo Auctions Japan, active listings only.

Built like the Datsun collector (listings/yahoo_auctions.py): the same URL
templates, query quoting (quote(), so a space is %20), headers, parts
word list and ¥100,000 floor for unscoped queries. Identity is classify()
on the title, which also reads Showa-era years (昭和55年 = 1980).

What the two probe rounds showed (2026-09-24):

- Round 1's open-search fetches answered HTTP 500; round 2's, built
  exactly as below (%20, Japanese Accept-Language), answered 200. The
  unscoped pages are the familiar server-rendered li.Product cards: 50
  per page for ハイラックス RN30 / 12R, every one a part, a manual or a
  model kit (all rejected by the parts list, the floor or classify()).
- The auccat=26360 (中古車・新車) URL no longer serves li.Product cards.
  It redirects to /carsearch?p=..., a Next.js car search whose
  __NEXT_DATA__ carries search.items.listing.items: title, price,
  categoryPath (ハイラックス is category 2084016685, ハイラックスサーフ
  2084016686) and carSpec.modelDate (YYYYMMDD, a structured first-
  registration date). featuredListing on the same page is promoted stock
  from any maker (a Crown and a Carry on probe day) and is ignored.
  parse_car_search() reads the listing items; the year from modelDate
  goes to classify() as a structured year.
- The closed (sold) search is not fetched: robots.txt disallows
  /closedsearch/ and the round-1 probe correctly refused it.

Fetch and parse are split so tests run the parsers against fixtures.
"""

from __future__ import annotations

import sys
import json
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.yahoo_auctions import (HEADERS, OPEN_URL, OPEN_VEHICLE_URL,
                                     _UNSCOPED_FLOOR_JPY, _looks_like_part)

SOURCE = "yahoo_auctions"
# Unscoped: the chassis code and engine code are what a Japanese seller of
# a 3rd-gen truck (or its parts) writes. "ハイラックス RN30" always has parts
# hits, so it doubles as the canary.
QUERIES = ["ハイラックス RN30", "ハイラックス 12R"]
# Vehicle category (answered by /carsearch): a bare ハイラックス there is
# page after page of modern trucks, so the queries lean on the words
# sellers of old ones use (旧車 = classic car; 昭和 = the Showa era).
# Probe day: 2 and 1 listing items respectively (a 1997 Delica whose
# title name-drops ハイラックス, a 2002 Xtracab, a 1985 diesel Surf).
VEHICLE_QUERIES = ["ハイラックス 旧車", "ハイラックス 昭和"]


def _record(auction_id: str, title: str, ident: dict, amount: float | None,
            image: str | None, fx_day: dict) -> dict:
    return {
        "id": f"yahoo_auctions:{auction_id}",
        "source": SOURCE,
        "source_listing_id": auction_id,
        "url": normalize.safe_url(f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}"),
        "title": title,
        "title_translated": None,
        "description_snippet": None,
        "year": ident["year"],
        "country": "JP",
        "region": None,
        "drive_side": normalize.infer_drive_side("JP", title),
        "king_cab": ident["king_cab"],
        "variant": ident["variant"],
        "price": normalize.make_price(amount, "JPY", fx_day),
        "images": [image] if image else [],
        "status": "active",
    }


def parse_open(html: str, fx_day: dict,
               vehicle_scoped: bool = False) -> tuple[list[dict], int]:
    """Active auctions from the open search page.
    Returns (records, raw_item_count); the raw count feeds the canary."""
    soup = BeautifulSoup(html, "html.parser")
    products = soup.select("li.Product")
    records = []
    for p in products:
        a = p.select_one("a.Product__titleLink")
        if a is None:
            continue
        auction_id = a.get("data-auction-id", "")
        title = a.get("data-auction-title") or a.get_text(" ", strip=True)
        if not auction_id:
            continue
        if not vehicle_scoped and _looks_like_part(title):
            continue
        ident = hilux.classify(title)
        if ident is None:
            continue

        raw_price = a.get("data-auction-price")
        amount = float(raw_price) if raw_price and raw_price.isdigit() else None
        if not vehicle_scoped and amount is not None and amount < _UNSCOPED_FLOOR_JPY:
            continue

        records.append(_record(auction_id, title, ident, amount,
                               a.get("data-auction-img"), fx_day))
    return records, len(products)


_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _model_year(item: dict) -> int | None:
    md = str((item.get("carSpec") or {}).get("modelDate") or "")
    return int(md[:4]) if re.match(r"(19|20)\d{2}", md) else None


def parse_car_search(html: str, fx_day: dict) -> tuple[list[dict], int]:
    """Whole-vehicle listings from the /carsearch page's __NEXT_DATA__.
    Returns (records, raw_item_count)."""
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("carsearch __NEXT_DATA__ missing (page layout changed?)")
    data = json.loads(m.group(1))
    try:
        listing = data["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]
    except (KeyError, TypeError):
        raise ValueError("carsearch listing block missing (page layout changed?)")
    items = listing.get("items") or []

    records = []
    for it in items:
        auction_id = it.get("auctionId") or ""
        title = it.get("title") or ""
        if not auction_id:
            continue
        if not any("中古車" in (c.get("name") or "") for c in it.get("categoryPath") or []):
            continue  # the vehicle tree only, as for the Datsun's sold items
        ident = hilux.classify(title, year=_model_year(it))
        if ident is None:
            continue
        amount = float(it["price"]) if it.get("price") else None
        image = it.get("imageUrl")
        records.append(_record(auction_id, title, ident, amount, image, fx_day))
    return records, len(items)


def parse_vehicle_page(html: str, fx_day: dict) -> tuple[list[dict], int]:
    """The auccat=26360 answer: the car search today; the old li.Product
    layout if Yahoo ever stops redirecting."""
    if _NEXT_RE.search(html) and "li class=\"Product" not in html:
        return parse_car_search(html, fx_day)
    return parse_open(html, fx_day, vehicle_scoped=True)


def search_urls() -> list[tuple[str, bool]]:
    """(url, vehicle_scoped) for every fetch, in order."""
    return ([(OPEN_URL.format(quote(q)), False) for q in QUERIES]
            + [(OPEN_VEHICLE_URL.format(quote(q)), True) for q in VEHICLE_QUERIES])


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    plan = search_urls()
    raw_total = 0
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for url, scoped in plan:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                recs, raw = (parse_vehicle_page(resp.text, fx_day) if scoped
                             else parse_open(resp.text, fx_day))
                raw_total += raw
                for rec in recs:
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{url}: {exc}")
    if failures and len(failures) == len(plan):
        raise RuntimeError(f"all Yahoo Hilux fetches failed ({failures[0]})")
    if failures:
        print(f"yahoo_auctions (hilux): partial failure, continuing without {failures}")
    if raw_total == 0:
        # "ハイラックス RN30" always has parts hits; zero raw items everywhere
        # means blocked or a layout change pretending to be an empty market.
        raise RuntimeError("canary: zero raw items across all Yahoo Hilux queries")
    return records
