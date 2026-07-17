"""Collector: Kaidee (rod.kaidee.com), Thailand's main classifieds site.

Thai context (docs/asia-sources.md): Thai-built 620s were badged Datsun
1300/1500, are nicknamed ช้างเหยียบ ("chang yiap"), and King Cab is written
คิงแค็บ. Listing years use the Buddhist Era and are routinely misconverted,
so year is extracted opportunistically but NEVER used to filter.

The car-category search (c11-auto-car?q=…) is server-rendered Next.js:
pageProps.ads carries id, title, numeric THB price, location and image.
Real matches lead the array and promoted unrelated ads pad it out, so
title filtering does the real work:

- a Datsun marker must be present (datsun / ดัทสัน / ช้างเหยียบ), and
- the King Cab filter must match (incl. คิงแค็บ), and
- other-generation markers (520/521/720/D21…) must be absent, because
  Thailand also had those trucks and "คิงแค็บ" alone spans generations.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "kaidee"
BASE = "https://rod.kaidee.com"
SEARCH_URL = BASE + "/c11-auto-car?q={}"
# Broad marque queries; the title filters do the narrowing.
QUERIES = ["datsun", "ดัทสัน"]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "th,en;q=0.8",
}

_DATSUN_MARKERS = ["datsun", "ดัทสัน", "ดัทซัน", "ช้างเหยียบ"]
# Digit boundaries matter: Buddhist Era years are everywhere in Thai titles
# and "ปี 2520" (= 1977) must not trip the 520 exclusion.
_OTHER_GEN_NUM_RE = re.compile(r"(?<!\d)(520|521|720)(?!\d)")
_OTHER_GEN_WORDS = ["d21", "d22", "big m", "big-m", "navara", "frontier", "จูเนียร์"]

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _wanted(title: str) -> bool:
    t = title.lower()
    if not any(m in t for m in _DATSUN_MARKERS):
        return False
    if _OTHER_GEN_NUM_RE.search(t) or any(g in t for g in _OTHER_GEN_WORDS):
        return False
    return king_cab.check(title)["matched"]


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    ads = (data.get("props", {}).get("pageProps", {}) or {}).get("ads") or []
    if not ads:
        # The search page always pads with promoted ads, so a truly empty
        # array means the payload moved, not an empty market.
        raise ValueError("zero ads in payload (page layout changed?)")

    records = []
    for ad in ads:
        title = ad.get("title", "") or ""
        ad_id = ad.get("id")
        if not ad_id or not _wanted(title):
            continue
        amount = float(ad["price"]) if ad.get("price") else None
        image = ad.get("image")

        records.append({
            "id": f"kaidee:{ad_id}",
            "source": SOURCE,
            "source_listing_id": str(ad_id),
            "url": normalize.safe_url(f"{BASE}/product-{ad_id}"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": normalize.extract_year(title),  # BE years excluded by design
            "country": "TH",
            "region": ad.get("location"),
            "drive_side": normalize.infer_drive_side("TH", title),
            "king_cab": king_cab.check(title),
            "price": normalize.make_price(amount, "THB", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for query in QUERIES:
            try:
                resp = client.get(SEARCH_URL.format(quote(query)))
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day):
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{query}: {exc}")
    if failures and len(failures) == len(QUERIES):
        raise RuntimeError(f"all Kaidee queries failed ({failures[0]})")
    if failures:
        print(f"kaidee: partial failure, continuing without {failures}")
    return records
