"""Collector: Bring a Trailer.

BaT embeds its auction list as JSON in the marque page (the
`auctionsCompletedInitialData` blob) — an approach proven by the v1.0 build.
We keep 620s passing the King Cab filter. Fetch and parse are split so tests
run the parser against a saved fixture page.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620

SOURCE = "bringatrailer"
URL = "https://bringatrailer.com/datsun/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


def parse_page(html: str, fx_day: dict) -> list[dict]:
    # BaT embeds LIVE auctions and completed ones in separate blobs; parsing
    # only the completed blob left running 620 auctions invisible until they
    # ended (2026-08-22 bug hunt). Either blob may be absent on a given page
    # build, but both missing means the layout changed.
    blobs = re.findall(
        r"var auctions(?:Completed|Current)InitialData = (\{.*?\});", html, re.S)
    if not blobs:
        raise ValueError("auction JSON blob not found (page layout changed?)")
    items = []
    for blob in blobs:
        items.extend(json.loads(blob).get("items", []))

    records = []
    for it in items:
        title = it.get("title", "")
        excerpt = it.get("excerpt", "")
        if not RE_620.search(title):
            continue
        # All 620 variants tracked; kc recorded for highlighting, not gating.
        kc = king_cab.check(title, excerpt)

        url = normalize.safe_url(it.get("url"))
        slug = url.rstrip("/").rsplit("/", 1)[-1] if url else title.lower().replace(" ", "-")
        country = normalize.to_country_code(it.get("country_code") or "US")
        amount = it.get("current_bid")
        currency = it.get("currency") or "USD"

        records.append({
            "id": f"bringatrailer:{slug}",
            "source": SOURCE,
            "source_listing_id": slug,
            "url": url,
            "title": title,
            "title_translated": None,
            "description_snippet": (excerpt[:500] or None),
            "year": (it.get("year") if isinstance(it.get("year"), int)
                     and 1971 <= it["year"] <= 1980 else normalize.extract_year(title)),
            "country": country,
            "region": None,
            "drive_side": normalize.infer_drive_side(country, f"{title} {excerpt}"),
            "king_cab": kc,
            "price": normalize.make_price(float(amount) if amount else None, currency, fx_day),
            "images": [it["thumbnail_url"]] if it.get("thumbnail_url") else [],
            "status": "active" if it.get("active") else "sold",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
