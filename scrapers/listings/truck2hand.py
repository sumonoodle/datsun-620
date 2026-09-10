"""Collector: Truck2Hand (Thailand), the Datsun pickup category.

Deferred in July 2026 as fully client-side; re-checked in September when
the owner asked for more Thai coverage and the verdict had aged out: the
category pages now ship complete listing data in __NEXT_DATA__
(listingSections = published ads, listingSoldSections = sold, each item
carrying hashId, Thai title, "฿ 92,000" display price, and shortDetails
like ["DATSUN","620","ปี 1974","กรุงเทพ"]).

The BRAND page is scraped rather than the 620 model facet: on fetch day
two real ช้างเหยียบ 620s (฿120k, ฿180k) carried no model tag and only the
brand page showed them. Title filtering does the model work — 620 or
ช้างเหยียบ counts, other generations are excluded, and the ปี year values
are ignored entirely (observed live: a 1974 truck tagged ปี 2020, a
mudguard tagged ปี 1937). A ฿10,000 floor plus a Thai parts word list
keeps parts out (the live ฿450 mudguard is the pinned case).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620, RE_OTHER_GEN

SOURCE = "truck2hand"
BASE = "https://www.truck2hand.com"
URL = f"{BASE}/category/cat_pickup+brand_brand-384-datsun/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "th,en;q=0.8",
}

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)
_PRICE_RE = re.compile(r"฿\s*([\d,]+)")
_FLOOR_THB = 10_000
# Parts words seen in the live feed and common in Thai truck-parts ads.
_PARTS_WORDS = ["กันโคลน", "อะไหล่", "ไฟท้าย", "ไฟหน้า", "กระจัง", "กันชน",
                "กระจก", "เบาะ", "ฝากระโปรง", "โช้ค", "แหนบ", "มือจับ",
                "ล้อแม็ก", "ยาง", "คิ้ว", "โลโก้", "ป้าย"]


def _iter_items(page_props: dict):
    for key, sold in (("listingSections", False), ("listingSoldSections", True)):
        for sec in page_props.get(key, []) or []:
            for row in sec.get("rows", []) or []:
                for item in row.get("items", []) or []:
                    yield item, sold


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    pp = (json.loads(m.group(1)).get("props", {}) or {}).get("pageProps", {}) or {}

    records = []
    seen: set[str] = set()
    found_any = False
    for item, sold_section in _iter_items(pp):
        found_any = True
        hash_id = item.get("hashId") or ""
        title = item.get("title") or ""
        details = " ".join(str(x) for x in item.get("shortDetails") or [])
        text = f"{title} {details}"
        if not hash_id or hash_id in seen:
            continue
        # 620 by number or by nickname; other generations out. shortDetails
        # is excluded from the generation check because its ปี years are
        # garbage (ปี 2020 on a 1974 truck) and would false-positive.
        if not (RE_620.search(text) or "ช้างเหยียบ" in title):
            continue
        if RE_OTHER_GEN.search(title):
            continue
        if any(w in title for w in _PARTS_WORDS):
            continue
        pm = _PRICE_RE.search(item.get("displayPrice") or "")
        amount = float(pm.group(1).replace(",", "")) if pm else None
        if amount is not None and amount < _FLOOR_THB:
            continue  # parts money, not truck money
        seen.add(hash_id)

        short = item.get("shortDetails") or []
        region = short[-1] if short and not str(short[-1]).startswith("ปี") else None
        sold = sold_section or item.get("itemSoldWorkflow") == "W8_ITEM_SOLD_STATE"

        records.append({
            "id": f"truck2hand:{hash_id}",
            "source": SOURCE,
            "source_listing_id": hash_id,
            "url": normalize.safe_url(f"{BASE}/listing/{hash_id}/"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": None,  # ปี values are unreliable by design (docs/asia-sources.md)
            "country": "TH",
            "region": region,
            "drive_side": normalize.infer_drive_side("TH", title),
            "king_cab": king_cab.check(title),
            "price": normalize.make_price(amount, "THB", fx_day),
            "images": [item["imageUrl"]] if item.get("imageUrl") else [],
            "status": "sold" if sold else "active",
        })
    if not found_any and "datsun" not in html.lower():
        raise ValueError("no items and page does not look like the Datsun category")
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
