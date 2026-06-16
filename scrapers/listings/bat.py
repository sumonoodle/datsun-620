"""Collector: Bring a Trailer Datsun auctions.

BaT embeds its auction list as JSON in the marque page (the
`auctionsCompletedInitialData` blob). We parse it and keep the 620s. Recall-first:
we filter only on the model (620), not on cab type; King Cab scoring happens later.
Returns both active and completed auctions; completed ones carry their sale price.
"""

from __future__ import annotations

import json
import re

import httpx

from common.listings_common import ListingResult

URL = "https://bringatrailer.com/datsun/"
SOURCE = "bringatrailer"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


def _is_620(title: str) -> bool:
    return bool(re.search(r"\b620\b", title or ""))


def collect() -> ListingResult:
    try:
        r = httpx.get(URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        r.raise_for_status()
        m = re.search(r"var auctionsCompletedInitialData = (\{.*?\});", r.text, re.S)
        if not m:
            return ListingResult(SOURCE, ok=False, note="auction JSON not found (layout changed?)")
        items = json.loads(m.group(1)).get("items", [])
    except Exception as e:  # noqa: BLE001
        return ListingResult(SOURCE, ok=False, note=f"fetch/parse failed: {e}")

    records = []
    for it in items:
        title = it.get("title", "")
        if not _is_620(title):
            continue
        records.append({
            "source": SOURCE,
            "source_url": it.get("url", ""),
            "title": title,
            "price_original": it.get("current_bid"),
            "currency": it.get("currency"),
            "country_code": it.get("country_code"),
            "year": it.get("year"),
            "photo_urls": [it["thumbnail_url"]] if it.get("thumbnail_url") else [],
            "status": "active" if it.get("active") else "sold",
            "description": it.get("excerpt", ""),
        })
    return ListingResult(SOURCE, ok=True, records=records)
