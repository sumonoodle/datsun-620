"""Hilux collector: 中古車EX (kuruma-ex.jp), ハイラックス model search, year-capped.

Same server-rendered div.car-item result cards as the Datsun collector
(listings/kuruma_ex.py), whose card helpers are shared, including its fix
for split-bold prices (the total-price-js value attribute).

The model code comes from the Toyota maker page the 2026-09-24 runner
probe fetched: its shashu links list S112 = ハイラックス (738 cars) and
S113 = ハイラックスサーフ (320). 738 modern trucks is far too many to page
through, so the search is capped with year_max=1984, a value taken from
the same page's own 年式 dropdown (it offers years down to 1982).

The round-2 probe confirmed the cap: ?year_max=1984 redirected to
/S112/year_max/1984 and returned one card, a 1971 ハイラックスデラックス
(1st gen), against 20 cards of 1990-2026 stock uncapped. It stays
guarded two ways:
a card newer than the cap means the parameter was ignored, which raises;
and a card-less page counts as an ordinary empty day only while the
search form is still on it (with the cap, zero results is the usual
answer, since the 3rd gen is rare).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.kuruma_ex import BASE, HEADERS, _ID_RE, _MAN_YEN_RE, _YEAR_RE

SOURCE = "kuruma_ex"
# 1989, not 1984: classify() accepts RN30/RN35/RN40/RN45 trucks registered
# up to hilux.LATE_YEAR_MAX, and 1989 is on the site's own dropdown.
YEAR_CAP = hilux.LATE_YEAR_MAX
# The path form is the site's canonical: ?year_max=N redirects to it.
URL = f"{BASE}/usedcar/search/result/maker/TO/shashu/S112/year_max/{YEAR_CAP}"


def parse_page(html: str, fx_day: dict, year_cap: int | None = YEAR_CAP) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.car-item")
    if not cards:
        if soup.select_one("form#usedcar_search") is None:
            raise ValueError("zero car-item cards and no search form (layout changed or blocked?)")
        return []

    records = []
    seen: set[str] = set()
    for card in cards:
        a = card.find("a", href=_ID_RE)
        if a is None:
            continue
        listing_id = _ID_RE.search(a["href"]).group(1)
        if listing_id in seen:
            continue
        text = card.get_text(" ", strip=True)
        # Title = maker + grade line, cut at the first price/spec label, as
        # in the Datsun collector.
        title = re.split(r"支払総額|本体価格|応談|年式", text)[0]
        title = " ".join(title.split())[:120]

        ym = _YEAR_RE.search(text)
        year = int(ym.group(1)) if ym else None
        if year_cap is not None and year is not None and year > year_cap:
            raise ValueError(f"card year {year} above year_max={year_cap}: year filter ignored")
        # Model-scoped search, so the name may be missing from a grade line.
        ident = hilux.classify(title, text[:300], year=year, require_name=False)
        if ident is None:
            continue
        seen.add(listing_id)

        amount = None
        price_el = card.select_one(".total-price-js[value]")
        if price_el and str(price_el.get("value", "")).isdigit():
            amount = float(price_el["value"])
        else:
            pm = _MAN_YEN_RE.search(text.replace(" ", ""))
            amount = float(pm.group(1).replace(",", "")) * 10_000 if pm else None
        if amount == 0:
            amount = None
        img = card.find("img")
        image = (img.get("data-src") or img.get("src") or "") if img else ""
        if image.startswith("//"):
            image = "https:" + image

        records.append({
            "id": f"kuruma_ex:{listing_id}",
            "source": SOURCE,
            "source_listing_id": listing_id,
            "url": normalize.safe_url(BASE + a["href"] if a["href"].startswith("/") else a["href"]),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", text),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
