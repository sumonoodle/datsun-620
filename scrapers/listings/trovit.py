"""Collector: Trovit Cars, the datsun-620 aggregator pages (US + DE).

Trovit aggregates other classifieds (dealer sites, Craigslist relays,
ClassicCars networks), so it is a SAFETY NET: 620s whose home site we
don't scrape surface here — the German edition notably syndicates from
bot-walled EU sites. Cards are server-rendered div.item elements with a
stable data-id, title, price, address and year; the markup is identical
across editions (verified US and DE 2026-08). Editions differ in
currency and thousands separator ("$15,550" vs "21.990 €"). The UK/ES/AU
editions were probed twice and have no guessable search path — only
verified editions are listed here.

One more edition-specific hazard, seen live on DE: an edition with no
Datsun matches pads the page with unrelated cars (Dacias, Skodas), so
the title-level 620 gate is what keeps an empty market honest.

Outbound links are tracking redirects — recorded as-is; the relist
detector pairs duplicates with their home-site records rather than us
trying to resolve redirect targets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620, RE_OTHER_GEN

SOURCE = "trovit"
# (edition, country, currency, url) — extend only with editions whose
# markup has been verified against a fetched page.
EDITIONS = [
    ("us", "US", "USD", "https://cars.trovit.com/used-cars/datsun-620"),
    ("de", "DE", "EUR", "https://de.trovit.com/autos/gebrauchtwagen/datsun-620"),
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}

_620_RE = RE_620
_OTHER_GEN_RE = RE_OTHER_GEN
_PRICE_DIGITS_RE = re.compile(r"([\d][\d.,]*)")


def _amount(text: str, currency: str) -> float | None:
    m = _PRICE_DIGITS_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    if currency == "EUR":  # German format: dot thousands ("21.990")
        raw = raw.replace(".", "").replace(",", ".")
    else:                  # US format: comma thousands ("15,550")
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_page(html: str, fx_day: dict, country: str = "US",
               currency: str = "USD") -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div.item.js-item")
    if not items:
        raise ValueError("zero items parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for it in items:
        item_id = it.get("data-id") or ""
        title_el = it.select_one(".item-title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        desc_el = it.select_one(".item-description-text")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        if not item_id or item_id in seen:
            continue
        # The page is 620-scoped, but aggregators drift: hold the line, and
        # in the TITLE — the live US page carried a "See Video at" stub card
        # whose only 620 lived in the description, and an edition with no
        # matches pads with unrelated cars entirely.
        if not _620_RE.search(title):
            continue
        if _OTHER_GEN_RE.search(title):
            continue
        seen.add(item_id)

        price_el = it.select_one(".actual-price")
        amount = _amount(price_el.get_text(strip=True), currency) if price_el else None
        addr_el = it.select_one(".item-address")
        region = addr_el.get_text(" ", strip=True) if addr_el else None
        a = it.find("a", href=True)
        img = it.select_one("img.snippet-image")
        image = img.get("src") if img else None
        if image and image.startswith("//"):
            image = "https:" + image

        records.append({
            "id": f"trovit:{item_id}",
            "source": SOURCE,
            "source_listing_id": item_id,
            "url": normalize.safe_url(a["href"] if a else EDITIONS[0][3]),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": normalize.extract_year(f"{title} {desc}"),
            "country": country,
            "region": region,
            "drive_side": normalize.infer_drive_side(country, f"{title} {desc}"),
            "king_cab": king_cab.check(title, desc),
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
                for rec in parse_page(resp.text, fx_day, country, currency):
                    if rec["id"] not in seen:  # editions can syndicate the same ad
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{edition}: {exc}")
    if failures and len(failures) == len(EDITIONS):
        raise RuntimeError(f"all Trovit editions failed ({failures[0]})")
    if failures:
        print(f"trovit: partial failure, continuing without {failures}")
    return records
