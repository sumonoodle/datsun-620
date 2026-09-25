"""Hilux collector: FLEX (flexnet.co.jp), freeword ハイラックス, oldest first.

Same server-rendered div.usdbox cards as the Datsun collector
(listings/flex.py): h3 title, sales blurb, 年式 in the details table, a
SOLD OUT badge. FLEX is a 4x4 specialist, and its freeword search is
loose: on the 2026-09-24 runner probe the 40 cards for ハイラックス were
mostly Land Cruisers, Hilux Surfs, Jimnys and 2021-2023 Hilux diesels,
across 9+ pages.

So the collector asks for sort=4, the page's own 年式が古い順 (oldest
first) option, taken verbatim from the probe page's sort dropdown. The
round-2 probe confirmed it: 40 cards running 1994 upward (Prados, 80s,
Surfs), so any 3rd-gen truck would lead page 1; one page is enough.

Year comes strictly from the details table, never the blurb, for the
reason the Datsun collector documents (a "restored in 2020" blurb must not
read as the model year). Price comes from the labelled 支払総額 span (see
_price_yen for why the Datsun collector's first-万円 regex is not reused).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.flex import HEADERS, _ID_RE, _MAN_YEN_RE, _YEAR_RE

SOURCE = "flex"
QUERY = "ハイラックス"
URL = "https://www.flexnet.co.jp/search/freeword/" + quote(QUERY) + "?sort=4"


def _price_yen(card, blurb: str) -> float | None:
    """支払総額 (drive-away total), else 車両価格 (vehicle price), from the
    labelled price spans. Not the first 万円 on the card: on the 2026-09-24
    probe page every card lists 諸費用 (fees, e.g. 19.4万円) BEFORE the
    vehicle and total prices, so a first-match regex reads the fees as the
    price. The old card-text regex (minus the blurb, so a "300万円かけて
    レストア" pitch can't win) is kept only as a last resort for cards
    without the spans."""
    spans = [card.select_one(sel) for sel in (".kakakutxt", ".kakakutxt_hontai")]
    for el in spans:
        m = re.search(r"[\d,]+(?:\.\d+)?", el.get_text(strip=True)) if el else None
        if m:
            amount = float(m.group(0).replace(",", "")) * 10_000
            return amount or None
    if any(spans):
        return None  # labelled but no number: 応談 (negotiable), not the fees
    price_scope = card.get_text(" ", strip=True)
    if blurb:
        price_scope = price_scope.replace(blurb, " ")
    pm = _MAN_YEN_RE.search(price_scope.replace(" ", ""))
    amount = float(pm.group(1).replace(",", "")) * 10_000 if pm else None
    return amount or None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.usdbox")
    if not cards:
        # FLEX's loose freeword always returns Surfs and modern Hiluxes, so
        # a card-less page is a layout change or a block, not a quiet day.
        raise ValueError("zero stock cards parsed (page layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        if listing_id in seen:
            continue
        title_el = card.select_one(".useditem__ttl h3")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        blurb_el = card.select_one(".useditem__ttl p")
        blurb = blurb_el.get_text(" ", strip=True) if blurb_el else ""

        detail = card.select_one(".usd_detailbox")
        detail_text = detail.get_text(" ", strip=True) if detail else ""
        ym = _YEAR_RE.search(detail_text)
        year = int(ym.group(1)) if ym else None
        # 年式 is structured: classify() rejects it when out of window.
        # The blurb is sales copy, so it joins the description (chassis
        # codes, ディーゼル) but classify() reads the title first.
        ident = hilux.classify(title, f"{blurb} {detail_text}", year=year)
        if ident is None:
            continue
        seen.add(listing_id)

        amount = _price_yen(card, blurb)
        img = card.select_one(".usd_phbox img")
        # Real photo is lazy-loaded (data-original); src is a 1px trans.gif
        # placeholder on the 2026-09-24 probe page.
        image = (img.get("data-original") or img.get("data-src") or img.get("src")) if img else None
        if image and image.endswith("trans.gif"):
            image = None
        sold = "SOLD OUT" in card.get_text()

        records.append({
            "id": f"flex:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            # Detail slugs contain Japanese; see listings/flex.py.
            "url": normalize.safe_url(quote(
                ("https://www.flexnet.co.jp" + a["href"]) if a["href"].startswith("/") else a["href"],
                safe=":/?&=%")),
            "title": title,
            "title_translated": None,
            "description_snippet": (blurb[:500] or None),
            "year": ident["year"],
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", f"{title} {blurb}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [image] if image else [],
            "status": "sold" if sold else "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
