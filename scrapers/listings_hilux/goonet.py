"""Hilux collector: Goo-net (goo-net.com), Japan's domestic used-car portal.

Distinct from goonet_exchange (the English export mirror, which lists only
stock whose dealer opted into export): this is the domestic inventory,
where a Japanese-market 3rd-gen Hilux (RN30/RN31 and their 4WD siblings,
sold new in Japan 1978-83) would be advertised first. Pages are EUC-JP
and server-rendered: each car is a <div class="search-card"
id="tr_<goo car id>"> with the title (ハイラックス + grade + free text), a
spec grid (年式 year, 排気量 displacement, ミッション) and the body price
in 万円 (units of ¥10,000).

Why these URLs. The 2026-09-24 probe of /usedcar/brand-TOYOTA/car-HILUX/
held 700 cars, 50 a page, and page 1 was all 120/220-series trucks from
2017-2026. The page's own model facet splits the stock into １２０系 (615),
２２０系 (47) and その他 ("other"), model--1-10104114: everything that is
neither current series, about 38 cars, one page. That facet is where a
1980 truck lives. The Goo-net Exchange index also links a separate
HILUX_PICK_UP model (the older pickup line); its domestic twin,
/usedcar/brand-TOYOTA/car-HILUX_PICK_UP/, is fetched too. Round 3
(2026-09-24) confirmed both with the same card markup: その他 held 7 cars
(2023-24 120-series, 2003/2000/1996 trucks and a 1970 1st-gen 初代 at
price ASK, proof that classic Hiluxes are filed there), and
HILUX_PICK_UP held 12 1990-97 double cabs. One failing does not sink the
other.

Guard: the page's Product ld+json states offerCount. Cards promised but
none parsed raises; a count of 0 returns nothing; a page with neither a
count nor a card raises.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "goonet"
BASE = "https://www.goo-net.com"
URLS = [
    f"{BASE}/usedcar/brand-TOYOTA/car-HILUX/model--1-10104114/",
    f"{BASE}/usedcar/brand-TOYOTA/car-HILUX_PICK_UP/",
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.8",
}

_OFFER_RE = re.compile(r'"offerCount"\s*:\s*"?(\d+)')
_YEAR_RE = re.compile(r"(19[5-9]\d|20[0-3]\d)")
_SHOWA_RE = re.compile(r"(?:昭和|S)\s*(\d{1,2})")
_MAN_YEN_RE = re.compile(r"([\d.]+)\s*万円")


def _nfkc(text: str) -> str:
    # Goo-net titles are full-width (ＲＮ３０, ４ＷＤ, １６００); classify()'s
    # patterns are ASCII, so fold to half-width first.
    return unicodedata.normalize("NFKC", text or "")


def _year(value: str) -> int | None:
    v = _nfkc(value)
    m = _YEAR_RE.search(v)
    if m:
        return int(m.group(1))
    m = _SHOWA_RE.search(v)
    return 1925 + int(m.group(1)) if m else None


def decode(content: bytes) -> str:
    return content.decode("euc_jp", errors="replace")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _OFFER_RE.search(html)
    offers = int(m.group(1)) if m else None
    soup = BeautifulSoup(html, "html.parser")
    cards = [c for c in soup.select("div.search-card") if (c.get("id") or "").startswith("tr_")]
    if not cards:
        if offers == 0:
            return []
        if offers:
            raise ValueError(f"page reports {offers} cars but no card was parsed")
        raise ValueError("no search cards and no offer count (page layout changed or blocked?)")

    records = []
    for card in cards:
        car_id = card["id"][3:]
        link = card.select_one("h3.search-card__title a")
        if not car_id or link is None:
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        spec = {}
        for row in card.select("div.search-card__spec-row"):
            k, v = row.select_one("dt"), row.select_one("dd")
            if k and v:
                spec[k.get_text(strip=True)] = v.get_text(" ", strip=True)
        year = _year(spec.get("年式", ""))
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        maker = card.select_one("p.search-card__maker")
        detail = " ".join(x for x in [spec.get("排気量", ""), spec.get("ミッション", "")] if x)
        # The model facet is server-side, so the (abbreviated) title need not
        # name the truck; the maker line vouches for Toyota.
        if maker and "トヨタ" not in maker.get_text():
            continue
        ident = hilux.classify(_nfkc(title), _nfkc(detail), year=year, require_name=False)
        if ident is None:
            continue

        body = card.select_one("p.search-card__price-value--body")
        pm = _MAN_YEN_RE.search(body.get_text("", strip=True)) if body else None
        amount = round(float(pm.group(1)) * 10000) if pm else None
        img = card.select_one("div.search-card__photo img")
        image = img.get("src") if img else None
        dealer = card.select_one("a.search-card__dealer-name")
        href = link.get("href") or ""

        records.append({
            "id": f"goonet:{car_id}",
            "source": SOURCE,
            "source_listing_id": car_id,
            "url": normalize.safe_url(f"{BASE}{href}" if href.startswith("/") else href),
            "title": title,
            "title_translated": None,
            "description_snippet": (" | ".join(x for x in [
                detail, dealer.get_text(strip=True) if dealer else ""] if x)[:500] or None),
            "year": ident["year"],
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(float(amount) if amount else None, "JPY", fx_day),
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
                for rec in parse_page(decode(resp.content), fx_day):
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{url}: {exc}")
    if failures and len(failures) == len(URLS):
        raise RuntimeError(f"all Goo-net Hilux pages failed ({failures[0]})")
    if failures:
        print(f"goonet (hilux): partial failure, continuing without {failures}")
    return records
