"""Hilux collector: Barn Finds, three tag RSS feeds.

Same editorial feed format as the 620 collector (listings/barnfinds.py,
whose item parsing is reused). Barn Finds tags inconsistently, so three
feeds are polled and de-duplicated by post slug:

- tag/toyota-hilux: the Hilux name (five posts on 2026-09-24, back to
  2019, including a 1979 "Toyota Pickup" that was tagged Hilux).
- tag/toyota-pickup: the US name (three posts; the same 1979 truck).
- tag/toyota: every Toyota write-up, the one of the three that is busy
  enough (20 posts, the newest the day before the probe) to carry a new
  truck before anyone tags it by model. None was a 3rd-gen on the day.

Titles are "Hook: 1979 Toyota Pickup", so the US name is in the title,
where classify() looks for it.
"""

from __future__ import annotations

import html as html_mod
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.barnfinds import (HEADERS, _HTML_TAG_RE, _IMG_RE, _ITEM_RE, _PRICE_RE,
                                _TAG_RES, _text)

SOURCE = "barnfinds"
FEEDS = [
    "https://barnfinds.com/tag/toyota-hilux/feed/",
    "https://barnfinds.com/tag/toyota-pickup/feed/",
    "https://barnfinds.com/tag/toyota/feed/",
]


def parse_feed(xml: str, fx_day: dict) -> list[dict]:
    if "<rss" not in xml:
        raise ValueError("not an RSS document (feed moved or blocked?)")
    records = []
    for block in _ITEM_RE.findall(xml):
        # Unescaped in full (the 620 side only swaps &#215;): "4&#215;4"
        # must read as 4x4 for the drive rules, and "&#8217;" as a quote.
        title = html_mod.unescape(_text(_TAG_RES["title"], block))
        link = _text(_TAG_RES["link"], block)
        desc_html = _text(_TAG_RES["description"], block)
        desc = _HTML_TAG_RE.sub(" ", desc_html)
        desc = " ".join(html_mod.unescape(desc).split())[:500]
        if not link:
            continue
        ident = hilux.classify(title, desc)
        if ident is None:
            continue
        slug = link.rstrip("/").rsplit("/", 1)[-1]

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
            "year": ident["year"],
            "country": "US",  # Barn Finds covers the US market almost exclusively
            "region": None,
            "drive_side": normalize.infer_drive_side("US", f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [im.group(1)] if im else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for url in FEEDS:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                for rec in parse_feed(resp.text, fx_day):
                    if rec["id"] not in seen:  # one post can carry several tags
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{url.split('/tag/', 1)[-1]}: {exc}")
    if failures and len(failures) == len(FEEDS):
        raise RuntimeError(f"all Barn Finds feeds failed ({failures[0]})")
    if failures:
        print(f"barnfinds (hilux): partial failure, continuing without {failures}")
    return records
