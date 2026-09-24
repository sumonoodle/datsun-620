"""Hilux collector: Truck2Hand (Thailand), keyword searches "hilux" and "ไฮลักซ์".

Same __NEXT_DATA__ payload as the Datsun collector (listings/truck2hand.py:
listingSections rows of items with hashId, title, "฿ 92,000" displayPrice
and shortDetails like ["TOYOTA","Hilux Vigo","ปี 2007","กรุงเทพ"]), so
its item walker and price regex are shared.

Why the keyword search and not the Toyota brand facet the Datsun side
uses: the Toyota brand id is not discoverable offline. The Datsun slug
(brand_brand-384-datsun) came from a live page, and neither 2026-09-24
probe page (cat_pickup, search?q=hilux) carries brand facet links; they
are built client-side. The keyword search is real and paginated
(/search/?q=hilux&page=N, 332 ads over 4 pages on probe day; round 2
confirmed page 2 in the same payload shape), so it is
read in full up to MAX_PAGES.

Probe-day content, for scale: every Hilux on both pages was a Revo, Vigo,
Tiger, Mighty-X or Hero (1990-2025), plus ฿10 parts ads. Thai titles
often carry no year, and the ปี tag in shortDetails is unreliable (a 1974
Datsun was tagged ปี 2020), so it is passed to classify() only as
description text: it can supply a 1978-84 year to a titled Hilux but never
overrides a title, and an out-of-window tag is simply not a year to
extract_year(). The ฿10,000 floor and Thai parts words are the Datsun
collector's, for the same reason (the ฿10 gear-lever ads on probe day).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.truck2hand import (BASE, HEADERS, _FLOOR_THB, _NEXT_RE, _PARTS_WORDS,
                                 _PRICE_RE, _iter_items)

SOURCE = "truck2hand"
# Latin and Thai spellings: the Thai search (ไฮลักซ์) returned 3 ads on the
# round-2 probe, titled only in Thai ("ไฮลักซ์วีโก้"), which the Latin
# search cannot match. One request, read to its own totalPages.
QUERIES = ["hilux", "ไฮลักซ์"]
MAX_PAGES = 8


def _page_props(html: str) -> dict:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    return (json.loads(m.group(1)).get("props", {}) or {}).get("pageProps", {}) or {}


def parse_page(html: str, fx_day: dict) -> list[dict]:
    pp = _page_props(html)
    if "listingSections" not in pp:
        raise ValueError("no listingSections in payload (page layout changed?)")

    records = []
    seen: set[str] = set()
    for item, sold_section in _iter_items(pp):
        hash_id = item.get("hashId") or ""
        title = item.get("title") or ""
        if not hash_id or hash_id in seen:
            continue
        short = [str(x) for x in item.get("shortDetails") or []]
        ident = hilux.classify(title, " ".join(short))
        if ident is None:
            continue
        if any(w in title for w in _PARTS_WORDS):
            continue
        pm = _PRICE_RE.search(item.get("displayPrice") or "")
        amount = float(pm.group(1).replace(",", "")) if pm else None
        if amount is not None and amount < _FLOOR_THB:
            continue  # parts money, not truck money
        seen.add(hash_id)

        region = short[-1] if short and not short[-1].startswith("ปี") else None
        sold = sold_section or item.get("itemSoldWorkflow") == "W8_ITEM_SOLD_STATE"

        records.append({
            "id": f"truck2hand:{hash_id}",
            "source": SOURCE,
            "source_listing_id": hash_id,
            "url": normalize.safe_url(f"{BASE}/listing/{hash_id}/"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "TH",
            "region": region,
            "drive_side": normalize.infer_drive_side("TH", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "THB", fx_day),
            "images": [item["imageUrl"]] if item.get("imageUrl") else [],
            "status": "sold" if sold else "active",
        })
    return records


def total_pages(html: str) -> int:
    try:
        return int(_page_props(html).get("totalPages") or 1)
    except (TypeError, ValueError):
        return 1


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    pages: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for query in QUERIES:
            url = f"{BASE}/search/?q={quote(query)}"
            resp = client.get(url)
            resp.raise_for_status()
            pages.append(resp.text)
            # totalPages comes from page 1's own payload (4 for hilux on
            # probe day, 1 for ไฮลักซ์).
            for n in range(2, min(total_pages(resp.text), MAX_PAGES) + 1):
                r = client.get(f"{url}&page={n}")
                r.raise_for_status()
                pages.append(r.text)
    for html in pages:
        for rec in parse_page(html, fx_day):
            if rec["id"] not in seen:
                seen.add(rec["id"])
                records.append(rec)
    return records
