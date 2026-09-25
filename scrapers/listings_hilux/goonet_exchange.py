"""Hilux collector: Goo-net Exchange (English export portal), Toyota model indexes.

Same server-rendered ul.list-listview cards as the Datsun collector
(listings/goonet_exchange.py), so the card helpers are shared. What
differs is the model index and the era gate:

- /usedcars/TOYOTA/HILUX/ is the modern truck. The 2026-09-24 runner
  probe returned 20 cards, every one a 2018-2026 Z / GR SPORT / BLACK
  RALLY diesel, newest first. A 1980 truck, if listed, would sit far down
  that index, so the Hilux name alone is not enough to find it.
- The same page links a second model, /usedcars/TOYOTA/HILUX_PICK_UP/
  (catalogue code 10104001), the older pickup line where a 1978-83 truck
  is likelier to be filed. The round-2 probe (2026-09-24) confirmed the
  identical ul.list-listview markup: 12 cards, 1990-1997 double and
  single cabs, the whole index on one page. It is fetched too.

The first detail cell is the registration date ("1980.03"), which on a
Japanese export portal is structured and reliable. A year outside the
Hilux window is dropped before identity is even asked, and classify()
then does the diesel / wrong-generation work on the title.

Fetch and parse are split so tests run the parser against a saved fixture.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.goonet_exchange import BASE, HEADERS, _YEN_RE, _card_year

SOURCE = "goonet_exchange"
# Model indexes, not a keyword search: both are Goo-net's own model pages.
URLS = [
    f"{BASE}/usedcars/TOYOTA/HILUX_PICK_UP/",
    f"{BASE}/usedcars/TOYOTA/HILUX/",
]

_ID_RE = re.compile(r"/usedcars/TOYOTA/(HILUX[A-Z_]*)/(\d+)/?$")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("ul.list-listview")
    if container is None:
        raise ValueError("listing container missing (page layout changed or blocked?)")

    records = []
    for li in container.find_all("li", recursive=False):
        a = li.find("a", href=_ID_RE)
        if a is None:
            continue
        model_slug, listing_id = _ID_RE.search(a["href"]).groups()
        title_el = li.select_one("h3.title")
        title = " ".join(title_el.get_text(" ", strip=True).split()) if title_el else ""
        details = [" ".join(d.get_text(" ", strip=True).split()) for d in li.select("ul.details li")]
        year = _card_year(details)
        # The registration date is structured: classify() rejects it when
        # out of window (and knows which chassis codes were registered late).
        ident = hilux.classify(title, " ".join(details), year=year, require_name=False)
        if ident is None:
            continue

        price_el = li.select_one("p.price")
        m = _YEN_RE.search(price_el.get_text(strip=True)) if price_el else None
        amount = float(m.group(1).replace(",", "")) if m else None

        detail_text = " ".join(details)
        drive = "RHD" if re.search(r"\bright\b", detail_text, re.I) else (
            "LHD" if re.search(r"\bleft\b", detail_text, re.I) else
            normalize.infer_drive_side("JP"))

        # The lazy-loaded photo, not the first <img>: "trusted dealer" and
        # "certified" badges sit in the same div on many HILUX cards
        # (2026-09-24 probe), and a badge PNG is not a picture of the truck.
        img = li.select_one("div.photo img.lazyload") or li.select_one("div.photo img")
        image = (img.get("data-src") or img.get("src")) if img else None
        location_el = li.select_one("p.location")

        records.append({
            "id": f"goonet_exchange:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(f"{BASE}/usedcars/TOYOTA/{model_slug}/{listing_id}/"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "JP",
            "region": location_el.get_text(strip=True) if location_el else None,
            "drive_side": drive,
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for url in URLS:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day):
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{url}: {exc}")
    if failures and len(failures) == len(URLS):
        raise RuntimeError(f"all Goo-net Exchange Hilux indexes failed ({failures[0]})")
    if failures:
        print(f"goonet_exchange (hilux): partial failure, continuing without {failures}")
    return records
