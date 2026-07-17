"""Collector: Barn Finds, the datsun-620 tag RSS feed.

Barn Finds is a human-curated blog: each post is a write-up of a real
listing (eBay, Craigslist, dealer) with photos and context — effectively a
free editorial alert layer over sources we cannot scrape directly. The
620 tag feed is polled; King Cab write-ups become records pointing at the
Barn Finds post (which links the live ad). Prices are rarely in the feed
excerpt, so most records carry no price — the digest renders that as
"no price shown". A post's subject may itself be on eBay, in which case
the relist detector may pair them; that is fine and honest.
"""

from __future__ import annotations

import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "barnfinds"
FEED_URL = "https://barnfinds.com/tag/datsun-620/feed/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
}

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_TAG_RES = {
    "title": re.compile(r"<title>(.*?)</title>", re.S),
    "link": re.compile(r"<link>(.*?)</link>", re.S),
    "description": re.compile(r"<description>\s*<!\[CDATA\[(.*?)\]\]>", re.S),
}
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PRICE_RE = re.compile(r"(?:asking|price of|listed (?:for|at)|BIN of)\s*\$([\d,]+)", re.I)


def _text(pattern: re.Pattern, block: str) -> str:
    m = pattern.search(block)
    return (m.group(1).strip() if m else "")


def parse_feed(xml: str, fx_day: dict) -> list[dict]:
    if "<rss" not in xml:
        raise ValueError("not an RSS document (feed moved or blocked?)")
    records = []
    for block in _ITEM_RE.findall(xml):
        title = _text(_TAG_RES["title"], block).replace("&#215;", "x").replace("&amp;", "&")
        link = _text(_TAG_RES["link"], block)
        desc_html = _text(_TAG_RES["description"], block)
        desc = _HTML_TAG_RE.sub(" ", desc_html)
        desc = " ".join(desc.split())[:500]
        if not link:
            continue
        slug = link.rstrip("/").rsplit("/", 1)[-1]

        kc = king_cab.check(title, desc)

        pm = _PRICE_RE.search(desc)
        amount = float(pm.group(1).replace(",", "")) if pm else None
        im = _IMG_RE.search(desc_html)

        records.append({
            "id": f"barnfinds:{slug}",
            "source": SOURCE,
            "source_listing_id": slug,
            "url": normalize.safe_url(link),
            "title": title,
            "title_translated": None,
            "description_snippet": desc or None,
            "year": normalize.extract_year(title),
            "country": "US",  # Barn Finds covers the US market almost exclusively
            "region": None,
            "drive_side": normalize.infer_drive_side("US", f"{title} {desc}"),
            "king_cab": kc,
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [im.group(1)] if im else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(FEED_URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_feed(resp.text, fx_day)
