"""Hilux collector: CAR FROM JAPAN (carfromjapan.com), Japanese exporter.

The model page is Next.js (app router). The rendered cards are thin, but
the React Server Components payload pushed through self.__next_f carries
the result list as JSON: a "cars" array of CarSchema objects with id,
carUrl, registrationYear, fuelKey (PETROL/DIESEL), driveTypeKey,
steeringKey, displacement, priceUSD and the JPY price, followed by the
search's totalCount.

Why ?maxYear=1985. The 2026-09-24 probe of the plain model page held 538
Hiluxes, 25 a page in 22 pages, in "Relevant" order; the oldest truck on
page 1 was a 1989 and most were 2018-2026. Round 3 tried two scopes:

- ?sortBy=registrationDate ("Year Old to New" in the sort select) is NOT
  applied server-side: the page came back with the same 25 ids in the
  same order as the unsorted page (the sort is client-side).
- ?maxYear=1985 IS applied server-side: the RSC payload shows the search
  params sent to the API ({"limit":25,"maxYear":1985,"makeModelKey":
  "toyota-hilux"}) and the cars array came back empty, which fits a stock
  whose oldest Hilux is a 1989. That is the polled URL: when a 1978-84
  truck is stocked it is the whole result set.

Guard: no "cars" array in the payload raises (layout change or block
page); a positive totalCount with an empty array raises. An empty array
counts as an empty market only when the payload also echoes the maxYear
search param (the filtered empty page carries no totalCount at all), so
an empty array from some other page shape raises.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "carfromjapan"
BASE = "https://carfromjapan.com"
URL = f"{BASE}/cheap-used-toyota-hilux-for-sale?maxYear=1985"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_PUSH_RE = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.S)
_TOTAL_RE = re.compile(r'"totalCount":(\d+)')
_MAXYEAR_RE = re.compile(r'"maxYear":"?\d{4}')


def _flight(html: str) -> str:
    """Concatenate the RSC string chunks pushed into self.__next_f."""
    out = []
    for raw in _PUSH_RE.findall(html):
        try:
            chunk = json.loads(raw)
        except ValueError:
            continue
        if len(chunk) > 1 and isinstance(chunk[1], str):
            out.append(chunk[1])
    return "".join(out)


def _cars(flight: str) -> tuple[list[dict], int | None]:
    i = flight.find('"cars":[')
    if i < 0:
        raise ValueError("no cars array in the RSC payload (page layout changed or blocked?)")
    cars, end = json.JSONDecoder().raw_decode(flight, i + len('"cars":'))
    m = _TOTAL_RE.search(flight, end)
    return cars, (int(m.group(1)) if m else None)


def parse_page(html: str, fx_day: dict) -> list[dict]:
    flight = _flight(html)
    cars, total = _cars(flight)
    if not cars:
        if total:
            raise ValueError(f"search reports {total} cars but none were parsed")
        if total is None and not _MAXYEAR_RE.search(flight):
            raise ValueError("empty cars array with no count and no year filter echo")
        return []

    records = []
    for car in cars:
        car_id = str(car.get("id") or "")
        if not car_id or car.get("__typename", "CarSchema") != "CarSchema":
            continue
        if str(car.get("makeKey") or "toyota").lower() != "toyota":
            continue
        year = car.get("registrationYear") or car.get("year")
        year = year if isinstance(year, int) else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        title = car.get("title") or f"Toyota Hilux {year or ''}".strip()
        fuel = str(car.get("fuelKey") or "").lower()
        drive = str(car.get("driveTypeKey") or "")
        cc = car.get("displacement")
        detail = " ".join(x for x in [
            car.get("modelCode") or "", fuel, drive,
            f"{cc}cc" if isinstance(cc, int) else ""] if x)
        ident = hilux.classify(title, detail, year=year, require_name=False)
        if ident is None:
            continue

        price = car.get("priceUSD")
        amount = float(price) if isinstance(price, (int, float)) and price > 0 else None
        steering = str(car.get("steeringKey") or "").upper()
        drive_side = {"RIGHT": "RHD", "LEFT": "LHD"}.get(steering) or normalize.infer_drive_side("JP")
        preview = car.get("imagePreview") or {}
        image = (f"https://{preview['cdnUri']}/{preview['filename']}"
                 if preview.get("cdnUri") and preview.get("filename") else None)
        path = car.get("carUrl") or ""

        records.append({
            "id": f"carfromjapan:{car_id}",
            "source": SOURCE,
            "source_listing_id": car_id,
            "url": normalize.safe_url(f"{BASE}{path}" if path.startswith("/") else path),
            "title": title,
            "title_translated": None,
            "description_snippet": (detail[:500] or None),
            "year": ident["year"],
            # CFJ exports from Japan; the stock record carries no yard location.
            "country": "JP",
            "region": None,
            "drive_side": drive_side,
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
