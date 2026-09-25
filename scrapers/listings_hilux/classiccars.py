"""Hilux collector: ClassicCars.com, two model-scoped searches.

Same JSON-LD search pages as the 620 collector (listings/classiccars.py,
whose car_blocks() is reused). ClassicCars files the North American truck
under "Pickup" and imports under "Hilux", so both are polled:

- /1978-1984/toyota/pickup: year-scoped server-side, so every card is in
  the window. The 2026-09-24 probe page held four cards, three of them
  3rd-gen trucks (1980, 1980, 1982) and a 1984 (4th gen in the US).
- /all-years/toyota/hilux: the imports. On 2026-09-24 it held three
  later trucks (1986, 1989, 1997), all correctly rejected.

Both searches are model-scoped, so titles need not name the model
(require_name=False); the structured modelDate is preferred as the year.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.classiccars import BASE, HEADERS, _PLACE_RE, car_blocks

SOURCE = "classiccars"
URLS = [
    f"{BASE}/listings/find/1978-1984/toyota/pickup",
    f"{BASE}/listings/find/all-years/toyota/hilux",
]

# '<title class="title">1978 to 1984 Toyota Pickup for Sale ...' and
# '<title class="title">Classic Toyota Hilux for Sale ...'.
_PAGE_TITLE_RE = re.compile(r"<title[^>]*>[^<]*Toyota[^<]*</title>", re.I)


def parse_page(html: str, fx_day: dict) -> list[dict]:
    blocks = car_blocks(html)
    if not blocks and not _PAGE_TITLE_RE.search(html):
        # A rare truck can leave a search empty; a page that isn't even a
        # Toyota search is a block or a move, and must not read as empty.
        raise ValueError("page does not look like the Toyota search (blocked or moved?)")

    records = []
    seen: set[str] = set()
    for d in blocks:
        sku = d.get("sku", "")
        name = d.get("name", "")
        desc = d.get("description", "")
        offer = d.get("offers") or {}
        if not sku or sku in seen:
            continue
        model_year = int(d["modelDate"]) if str(d.get("modelDate", "")).isdigit() else None
        ident = hilux.classify(name, desc, year=model_year, require_name=False)
        if ident is None:
            continue
        seen.add(sku)

        path = offer.get("url") or ""
        region = None
        pm = _PLACE_RE.search(path)
        if pm:
            region = pm.group(1).replace("-", " ").title()
        try:
            amount = float(offer["price"]) if offer.get("price") else None
        except (ValueError, TypeError):
            amount = None
        image = (d.get("image") or {}).get("url")

        records.append({
            "id": f"classiccars:{sku}",
            "source": SOURCE,
            "source_listing_id": sku,
            "url": normalize.safe_url(BASE + path if path.startswith("/") else path),
            "title": name,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": ident["year"],
            "country": "US",
            "region": region,
            "drive_side": normalize.infer_drive_side("US", f"{name} {desc}"),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, offer.get("priceCurrency") or "USD", fx_day),
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
                failures.append(f"{url.rsplit('/', 1)[-1]}: {exc}")
    if failures and len(failures) == len(URLS):
        raise RuntimeError(f"all ClassicCars searches failed ({failures[0]})")
    if failures:
        print(f"classiccars (hilux): partial failure, continuing without {failures}")
    return records
