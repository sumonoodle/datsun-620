"""Hilux collector: Bring a Trailer, the Toyota Pickup keyword page.

BaT has no Hilux page (/toyota/hilux/ is a 404, 2026-09-24 probe). The
Toyota marque page is no use either: 10,889 completed auctions at 24 a
page, so a 1981 truck would scroll off within hours. /toyota/pickup/ is
BaT's own grouping of every Toyota truck (Pickup, Hilux, Tacoma, T100,
Tundra: 1,983 auctions), so a 3rd-gen truck lands there whichever name
the seller used; the probe page carried a "1990 Toyota Hilux" and a
"1992 Toyota Hilux SSR" next to the US-named Pickups.

The page carries auctions two ways, and both are read:
- COMPLETED auctions as the `auctionsCompletedInitialData` JSON blob
  (the same blob the 620 collector parses; listings/bat.py).
- LIVE auctions as server-rendered cards under "Toyota Pickup Live
  Auctions (N)". The 2026-09-24 page had no auctionsCurrentInitialData
  blob at all, and its only 3rd-gen truck was LIVE: "1981 Toyota Pickup
  SR-5 4x4 5-Speed". A blob-only parser would not have seen it until the
  hammer fell.

Titles are HTML-unescaped before classify(): BaT writes "4&#215;4" in the
JSON, which hides the 4WD signal from the drive rules.
"""

from __future__ import annotations

import html as html_mod
import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.bat import UA

SOURCE = "bringatrailer"
URL = "https://bringatrailer.com/toyota/pickup/"

_BLOB_RE = re.compile(r"var auctions(?:Completed|Current)InitialData = (\{.*?\});", re.S)
# "Toyota Pickup Live Auctions (10)"
_LIVE_COUNT_RE = re.compile(r"Live Auctions \((\d+)\)")
_BID_RE = re.compile(r"([A-Z]{3})\s*\$?([\d,]+)")


def _slug(url: str, title: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1] if url else title.lower().replace(" ", "-")


def _record(*, url: str, title: str, excerpt: str, country: str, amount: float | None,
            currency: str, image: str | None, active: bool, ident: dict,
            fx_day: dict) -> dict:
    slug = _slug(url, title)
    return {
        "id": f"bringatrailer:{slug}",
        "source": SOURCE,
        "source_listing_id": slug,
        "url": url,
        "title": title,
        "title_translated": None,
        "description_snippet": (excerpt[:500] or None),
        "year": ident["year"],
        "country": country,
        "region": None,
        "drive_side": normalize.infer_drive_side(country, f"{title} {excerpt}"),
        "king_cab": ident["king_cab"],
        "variant": ident["variant"],
        "price": normalize.make_price(amount, currency, fx_day),
        "images": [image] if image else [],
        "status": "active" if active else "sold",
    }


def _blob_records(page: str, fx_day: dict) -> list[dict]:
    blobs = _BLOB_RE.findall(page)
    if not blobs:
        raise ValueError("auction JSON blob not found (page layout changed?)")
    records = []
    for blob in blobs:
        for it in json.loads(blob).get("items", []):
            title = html_mod.unescape(it.get("title", ""))
            excerpt = html_mod.unescape(it.get("excerpt", "") or "")
            year = it.get("year") if isinstance(it.get("year"), int) else None
            ident = hilux.classify(title, excerpt, year=year)
            if ident is None:
                continue
            amount = it.get("current_bid")
            records.append(_record(
                url=normalize.safe_url(it.get("url")), title=title, excerpt=excerpt,
                country=normalize.to_country_code(it.get("country_code") or "US"),
                amount=float(amount) if amount else None,
                currency=it.get("currency") or "USD",
                image=it.get("thumbnail_url"), active=bool(it.get("active")),
                ident=ident, fx_day=fx_day))
    return records


def _live_records(page: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(page, "html.parser")
    section = soup.select_one("div.listings-live")
    heading = section.find("h2") if section else None
    m = _LIVE_COUNT_RE.search(heading.get_text(" ", strip=True)) if heading else None
    claimed = int(m.group(1)) if m else 0
    cards = section.select("div.listing-card[data-listing_id]") if section else []
    # Same principle as the Kleinanzeigen guard: a heading promising live
    # auctions with no card parsed means the card markup moved, and must
    # not read as "no live trucks".
    if claimed and not cards:
        raise ValueError(f"heading claims {claimed} live auction(s) but no card parsed")

    records = []
    for card in cards:
        link = card.select_one("h3 a[href]")
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        ex = card.select_one(".item-excerpt")
        excerpt = ex.get_text(" ", strip=True) if ex else ""
        ident = hilux.classify(title, excerpt)
        if ident is None:
            continue
        flag = card.select_one(".item-tag-currency img[alt]")
        country = normalize.to_country_code(flag["alt"] if flag else "US")
        if country == "XX":
            country = "US"  # BaT is a US auction house; unknown flag = US
        bid = card.select_one(".bid-formatted")
        bm = _BID_RE.search(bid.get_text(" ", strip=True)) if bid else None
        img = card.select_one(".thumbnail img[src]")
        records.append(_record(
            url=normalize.safe_url(link["href"]), title=title, excerpt=excerpt,
            country=country,
            amount=float(bm.group(2).replace(",", "")) if bm else None,
            currency=bm.group(1) if bm else "USD",
            image=img["src"] if img else None, active=True,
            ident=ident, fx_day=fx_day))
    return records


def parse_page(page: str, fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    # Live first: an auction present both ways is live, and its card bid is
    # the fresher figure.
    for rec in _live_records(page, fx_day) + _blob_records(page, fx_day):
        if rec["id"] not in seen:
            seen.add(rec["id"])
            records.append(rec)
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
