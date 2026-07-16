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

SOURCE = "bringatrailer"
URL = "https://bringatrailer.com/datsun/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = re.search(r"var auctionsCompletedInitialData = (\{.*?\});", html, re.S)
    if not m:
        raise ValueError("auction JSON blob not found (page layout changed?)")
    items = json.loads(m.group(1)).get("items", [])

    records = []
    for it in items:
        title = it.get("title", "")
        excerpt = it.get("excerpt", "")
        if not re.search(r"\b620\b", title):
            continue
        kc = king_cab.check(title, excerpt)
        if not kc["matched"]:
            continue

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
