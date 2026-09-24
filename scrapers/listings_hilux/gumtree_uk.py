"""Hilux collector: Gumtree UK, keyword "toyota hilux", petrol and newest first.

The results page is server-rendered and ships its whole state as
`window.clientData = "<url-encoded JSON>"`: resultsPage.searchAds holds
every card with title, price, path, location, shortDescription and a
structured attributes list (vehicle_registration_year, vehicle_fuel_type,
vehicle_make). The rendered HTML carries only three titles as <img alt>,
so the JSON blob, not the markup, is what is parsed.

What it polls, and why it is weak. The 2026-09-24 probe fetched
/cars-vans-motorbikes/uk/srpsearch+toyota+hilux: 379 ads in 16 pages,
sorted by relevance, and page 1 was 26 cards of 2002-2025 D-4D diesels
(plus a Ford Ranger and an L200 whose titles mention the Hilux). The
payload's own filter links (vehicle_fuel_type=petrol: 1 petrol ad against
118 diesel; sortFilter "date": newest first) would fix that, but they all
live under /search?, and robots.txt disallows /search for our user agent
(round 3: both /search URLs were refused by the probe's robotparser and
never fetched). So only path-style /srpsearch+<keywords> URLs are polled:

- the probed Hilux search itself (page 1, relevance order: a 1980 truck
  appears only if Gumtree ranks it on page 1), and
- narrow keyword variants, where a 3rd-gen truck's own words ("rn30",
  "classic") are what the seller writes, so relevance works for us.

The keyword variants share the robots-allowed /srpsearch+ path prefix
but were not themselves fetched yet; a fuel/sort filter on the path form
is on the round-4 list. Treat this source as best-effort until then.
The registration-year facet cannot help: its lowest choice is "Before
2007".

Guard: clientData missing raises (layout change or block page). The
search's own total (adsTitle.totalNumberOfAdsFound) is compared with the
cards parsed: results promised but no card read raises; zero results is
an empty market and returns nothing.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "gumtree_uk"
BASE = "https://www.gumtree.com"
# Never /search? -- robots.txt disallows it (round-3 probe).
_SRP = f"{BASE}/cars-vans-motorbikes/uk/srpsearch+"
URLS = [
    f"{_SRP}toyota+hilux",          # round-1 probe: 200, robots-allowed
    f"{_SRP}toyota+hilux+rn30",
    f"{_SRP}toyota+hilux+classic",
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_CLIENT_DATA_RE = re.compile(r'window\.clientData\s*=\s*"(.*?)";', re.S)
_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")
# Vehicle categories only. Toys, manuals and parts are "for-sale" ads
# (/p/toys/..., /p/car-parts/...), which the keyword search also returns.
_VEHICLE_PATHS = ("/p/cars/", "/p/vans/", "/p/motors/", "/p/campervans-motorhomes/")


def _client_data(html: str) -> dict:
    m = _CLIENT_DATA_RE.search(html)
    if not m:
        raise ValueError("window.clientData missing (page layout changed or blocked?)")
    return json.loads(urllib.parse.unquote(m.group(1)))


def _total(results_page: dict) -> int | None:
    raw = (results_page.get("adsTitle") or {}).get("totalNumberOfAdsFound")
    if raw is None:
        raw = results_page.get("searchResultAbundance")
    try:
        return int(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    data = _client_data(html)
    results_page = data.get("resultsPage") or {}
    ads = results_page.get("searchAds")
    total = _total(results_page)
    if ads is None:
        raise ValueError("resultsPage.searchAds missing (payload moved?)")
    if not ads:
        if total:
            raise ValueError(f"search reports {total} ads but none were parsed")
        return []

    records = []
    for ad in ads:
        ad_id = str(ad.get("id") or "")
        path = ad.get("path") or ""
        if not ad_id or not path.startswith(_VEHICLE_PATHS):
            continue
        attrs = {a.get("key"): str(a.get("value") or "") for a in ad.get("attributes") or []}
        title = (ad.get("title") or "").strip()
        desc = (ad.get("shortDescription") or "").strip()
        make = attrs.get("vehicle_make", "")
        # Another make's ad that mentions the Hilux ("2007 Ford Ranger ...
        # PX HILUX" on the probe page) is not a Hilux, whatever the text.
        if make and make.lower() != "toyota":
            continue
        year_raw = attrs.get("vehicle_registration_year", "")
        year = int(year_raw) if year_raw.isdigit() else None
        # A structured registration year outside the window is decisive: it
        # comes from the DVLA lookup, not the seller's prose.
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        fuel = attrs.get("vehicle_fuel_type", "")
        ident = hilux.classify(title, f"{desc} {fuel}".strip(), year=year)
        if ident is None:
            continue

        price_raw = ad.get("price") or ""
        m = _PRICE_RE.search(str(price_raw))
        amount = float(m.group(0).replace(",", "")) if m else None
        image = ad.get("imageUrl")

        records.append({
            "id": f"gumtree_uk:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(f"{BASE}{path}"),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": "GB",
            "region": ad.get("location") or None,
            "drive_side": normalize.infer_drive_side("GB", f"{title} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "GBP", fx_day),
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
        raise RuntimeError(f"all Gumtree UK Hilux searches failed ({failures[0]})")
    if failures:
        print(f"gumtree_uk (hilux): partial failure, continuing without {failures}")
    return records
