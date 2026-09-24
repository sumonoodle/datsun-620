"""Hilux collector: Yahoo Auctions Japan, open (active) search only.

Built exactly like the Datsun collector (listings/yahoo_auctions.py): the
same URL templates, query quoting (quote(), so a space is %20), headers
and li.Product card parsing, and the same two-layer defence. Unscoped
queries catch a truck listed outside the vehicle category but are mostly
parts, so they get the Japanese parts word list and the ¥100,000 floor;
queries scoped to auccat=26360 (中古車・新車, whole vehicles) trust the
category instead. Identity is classify() on the title, which also reads
Showa-era years (昭和55年 = 1980), as Japanese auction titles often use.

Two differences from the Datsun collector, both from the 2026-09-24
runner probe:

- The closed (sold) search is not fetched. robots.txt disallows
  /closedsearch/ and the probe correctly refused it.
- The probe's two open-search fetches both answered HTTP 500. Its URLs
  differed from this collector's in two ways (a '+'-joined query and
  English Accept-Language), while the Datsun collector's identically
  built URLs succeed daily, so the exact URLs below go into the next
  probe round. Until then, a whole-run failure raises as usual.

Fetch and parse are split so tests run the parser against a fixture.
"""

from __future__ import annotations

import sys
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
# Vehicle category: a bare ハイラックス there is page after page of modern
# trucks, so the queries lean on the words sellers of old ones use
# (旧車 = classic car; 昭和 = the Showa era, 1926-1989).
VEHICLE_QUERIES = ["ハイラックス 旧車", "ハイラックス 昭和"]


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

        image = a.get("data-auction-img")
        records.append({
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
        })
    return records, len(products)


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
                recs, raw = parse_open(resp.text, fx_day, vehicle_scoped=scoped)
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
