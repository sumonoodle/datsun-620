"""Collector: Cars & Bids (tier 2, degradable).

Cars & Bids is a JS-heavy SPA behind bot protection that served HTTP 403 to
GitHub runners throughout the v1.0 build. Strategy: hit their public search
API endpoint first (JSON), fall back to the auctions page looking for embedded
state. Blocks raise and are absorbed by per-source isolation; the JSON parse
contract is pinned by a fixture test.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "carsandbids"
API_URL = "https://carsandbids.com/v2/autos/auctions"
PAGE_URL = "https://carsandbids.com/search/datsun%20620"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "en-GB,en;q=0.9",
}


def parse_auctions(payload: dict, fx_day: dict) -> list[dict]:
    """Parse a Cars & Bids auctions JSON payload (contract set by fixture)."""
    auctions = payload.get("auctions") or payload.get("results") or []
    records = []
    for a in auctions:
        title = a.get("title") or ""
        subtitle = a.get("sub_title") or a.get("subtitle") or ""
        if not re.search(r"\b620\b", title):
            continue
        kc = king_cab.check(title, subtitle)
        if not kc["matched"]:
            continue

        slug = a.get("slug") or str(a.get("id", ""))
        bid = (a.get("current_bid") or {})
        amount = bid.get("amount") if isinstance(bid, dict) else bid
        location = a.get("location") or {}
        country = normalize.to_country_code(
            location.get("country") if isinstance(location, dict) else "US"
        ) if location else "US"
        img = a.get("main_photo") or {}

        records.append({
            "id": f"carsandbids:{slug}",
            "source": SOURCE,
            "source_listing_id": str(slug),
            "url": f"https://carsandbids.com/auctions/{slug}",
            "title": title,
            "title_translated": None,
            "description_snippet": (subtitle[:500] or None),
            "year": a.get("year") or normalize.extract_year(title),
            "country": country if country != "XX" else "US",
            "region": location.get("state") if isinstance(location, dict) else None,
            "drive_side": normalize.infer_drive_side("US", f"{title} {subtitle}"),
            "king_cab": kc,
            "price": normalize.make_price(
                float(amount) if amount else None, "USD", fx_day
            ),
            "images": [img["url"]] if isinstance(img, dict) and img.get("url") else [],
            "status": "active" if not a.get("ended") else "sold",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(API_URL, params={"q": "datsun 620"})
        if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
            return parse_auctions(resp.json(), fx_day)
        if resp.status_code in (403, 429, 503):
            raise RuntimeError(f"HTTP {resp.status_code} (bot protection / blocked)")

        # Fallback: search page with embedded state.
        resp = client.get(PAGE_URL)
        if resp.status_code in (403, 429, 503):
            raise RuntimeError(f"HTTP {resp.status_code} (bot protection / blocked)")
        resp.raise_for_status()
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", resp.text, re.S)
        if not m:
            raise RuntimeError("no JSON API and no embedded state found (needs JS rendering?)")
        return parse_auctions(json.loads(m.group(1)), fx_day)
