"""Hilux collector: Retro Rides forum (UK), the cars-for-sale boards.

The same ProBoards boards the 620 collector reads (listings/retrorides.py:
board 57 "1985 & older", plus board 58 for misfiled posts), filtered for
the Hilux instead. Board convention puts year, make, model, price and
place in the thread title ("1978 Datsun 620 Pickup long bed. £8995
Sussex"), so the title is all classify() gets, and it must name the truck
(require_name=True): the board is every make, and the 2026-09-24 page
carried a "1978 Toyota Chaser E-TX41" that is not a pickup.

No Hilux was on board 57 on the probe day (35 threads); the test uses a
labelled synthetic thread.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize
from listings.retrorides import BASE, BOARDS, HEADERS, _THREAD_RE, _price

SOURCE = "retrorides"


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = [a for a in soup.find_all("a", href=_THREAD_RE)
               if len(a.get_text(strip=True)) > 10]
    if not anchors:
        raise ValueError("zero threads parsed (board layout changed or blocked?)")

    records = []
    seen: set[str] = set()
    for a in anchors:
        thread_id = _THREAD_RE.search(a["href"]).group(1)
        title = a.get_text(" ", strip=True)
        if thread_id in seen:
            continue
        ident = hilux.classify(title)
        if ident is None:
            continue
        seen.add(thread_id)

        url = a["href"]
        if url.startswith("/"):
            url = BASE + url

        records.append({
            "id": f"retrorides:{thread_id}",
            "source": SOURCE,
            "source_listing_id": thread_id,
            "url": normalize.safe_url(url),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "GB",
            "region": None,
            "drive_side": normalize.infer_drive_side("GB", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(_price(title), "GBP", fx_day),
            "images": [],
            "status": "sold" if re.search(r"\bSOLD\b", title, re.I) else "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for board in BOARDS:
            try:
                resp = client.get(board)
                resp.raise_for_status()
                for rec in parse_page(resp.text, fx_day):
                    if rec["id"] not in seen:
                        seen.add(rec["id"])
                        records.append(rec)
            except Exception as exc:
                failures.append(f"{board.rsplit('/', 1)[-1]}: {exc}")
    if failures and len(failures) == len(BOARDS):
        raise RuntimeError(f"all Retro Rides boards failed ({failures[0]})")
    if failures:
        print(f"retrorides (hilux): partial failure, continuing without {failures}")
    return records
