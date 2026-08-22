"""Collector: PistonHeads (UK), Datsun marque page.

The relaunched PistonHeads is Next.js with an Apollo cache: every card on
/buy/datsun is an Advert:<id> entity carrying headline, native GBP price,
year, images and a specificationData block with bodyType. Datsun stock is
small (a handful of Z-cars most days), so the whole marque page is polled
and 620s are picked out by title/description — or structurally, by a
Pickup body in the 620 era, which catches a UK ad titled just "Datsun
Pick-up". Other generations (520/521/720) are excluded by name.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "pistonheads"
URL = "https://www.pistonheads.com/buy/datsun"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', re.S)
_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_OTHER_GEN_RE = re.compile(r"(?<!\d)(?:520|521|720)(?!\d)|D2[12]", re.I)


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = (data.get("props", {}).get("pageProps", {}) or {}).get("__APOLLO_STATE__") or {}
    adverts = [v for k, v in apollo.items() if k.startswith("Advert:")]
    if not adverts and "datsun" not in html.lower():
        raise ValueError("no adverts and page does not look like the Datsun search")

    records = []
    for ad in adverts:
        ad_id = str(ad.get("id") or "")
        headline = ad.get("headline") or ""
        desc = ad.get("shortDescription") or ""
        model = ad.get("modelAnalyticsName") or ""
        spec = ad.get("specificationData") or {}
        year = ad.get("year") if isinstance(ad.get("year"), int) else None
        text = f"{headline} {model} {desc}"
        if not ad_id:
            continue
        if _OTHER_GEN_RE.search(text):
            continue
        is_620 = bool(_620_RE.search(text))
        is_era_pickup = (str(spec.get("bodyType") or "").lower() in ("pickup", "pick-up")
                        and year is not None and 1971 <= year <= 1980)
        if not (is_620 or is_era_pickup):
            continue

        price = ad.get("price")
        amount = float(price) if isinstance(price, (int, float)) else None
        currency = ad.get("currencyCode") or "GBP"
        images = [u for u in (ad.get("fullSizeImageUrls") or [])[:1] if u]

        records.append({
            "id": f"pistonheads:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(ad.get("url") or f"https://www.pistonheads.com/buy/listing/{ad_id}"),
            "title": headline,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": year if year and 1971 <= year <= 1980 else normalize.extract_year(text),
            "country": "GB",
            "region": None,
            "drive_side": normalize.infer_drive_side("GB", text),
            "king_cab": king_cab.check(headline, desc),
            "price": normalize.make_price(amount, currency, fx_day),
            "images": images,
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
