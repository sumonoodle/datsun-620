"""Hilux collector: Trovit Cars, the toyota-hilux pages (US, UK, DE).

Same aggregator markup as the 620 collector (listings/trovit.py, whose
extract_cards() and _amount() are reused). What the 2026-09-24 probe
found per edition:

- US (cars.trovit.com): "14 used Toyota Hilux cars", and the richest
  Hilux page of any Western source: seven 3rd-gen trucks, several titled
  with both names ("1982 Toyota Pickup Hilux SR5", "TOYOTA Pickup Hi Lux
  SR-5 1982 4X4"). The other 11 cards are padding (2026 Rams, F-150s).
  /used-cars/toyota-pickup is a 404, so the Hilux page is the US page.
- UK (cars.trovit.co.uk, new this round): 628 results, page 1 all
  current-shape diesels. Polled because it syndicates UK dealers we do
  not scrape. "?max_year=1984" (probe round 2) is ignored: same 628
  results, same cards in the same order.
- DE (de.trovit.com): no Hilux matched; the page was entirely padding
  (Skodas, Hyundais). Kept, as on the 620 side, because DE syndicates
  bot-walled EU sites and padding costs nothing: classify() drops it.

The gate is on the TITLE (description can't name the truck on its own),
for the 620 collector's reason: padding cards and stub cards.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.trovit import HEADERS, _amount, extract_cards

SOURCE = "trovit"
# (edition, country, currency, url). Only editions verified against a
# fetched page (2026-09-24); AU and ZA do not resolve.
EDITIONS = [
    ("us", "US", "USD", "https://cars.trovit.com/used-cars/toyota-hilux"),
    ("uk", "GB", "GBP", "https://cars.trovit.co.uk/used-cars/toyota-hilux"),
    ("de", "DE", "EUR", "https://de.trovit.com/autos/gebrauchtwagen/toyota-hilux"),
]


def parse_page(html: str, fx_day: dict, country: str = "US", currency: str = "USD",
               page_url: str = EDITIONS[0][3]) -> list[dict]:
    records = []
    seen: set[str] = set()
    for card in extract_cards(html):
        item_id = card["id"]
        title = card["title"]
        desc = card["desc"]
        if not item_id or item_id in seen:
            continue
        # Name and year must come from the title; the description only
        # informs the variant (drive, engine, cab).
        if hilux.classify(title) is None:
            continue
        ident = hilux.classify(title, desc)
        if ident is None:
            continue
        seen.add(item_id)

        price_text = card["price_text"]
        amount = _amount(price_text, currency) if price_text is not None else None
        image = card["image"]

        records.append({
            "id": f"trovit:{item_id}",
            "source": SOURCE,
            "source_listing_id": item_id,
            "url": normalize.safe_url(card["href"] or page_url),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": country,
            "region": card["region"] or None,
            "drive_side": normalize.infer_drive_side(country, f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, currency, fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for edition, country, currency, url in EDITIONS:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day, country, currency, url):
                    if rec["id"] not in seen:  # editions can syndicate the same ad
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{edition}: {exc}")
    if failures and len(failures) == len(EDITIONS):
        raise RuntimeError(f"all Trovit editions failed ({failures[0]})")
    if failures:
        print(f"trovit (hilux): partial failure, continuing without {failures}")
    return records
