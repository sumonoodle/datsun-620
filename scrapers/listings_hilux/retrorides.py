"""Hilux collector: Retro Rides forum (UK), the "1985 & older" sale board.

The same ProBoards markup the 620 collector reads (listings/retrorides.py),
filtered for the Hilux instead. Board 57 only: a 1978-83 truck belongs
there, and board 58 ("/board/58/cars-sale", which the 620 collector also
polls for misfiled posts) parsed zero threads on the first live branch
run while board 57 parsed fine. Both collectors share the parsing code
and board 58 was never in a probe round, so that is a question about the
board URL, not this module; see the report. Polling it here would only
add a daily partial failure for a board that cannot hold our truck. Board convention puts year, make, model, price and
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
from listings.retrorides import BASE, HEADERS, _THREAD_RE, _price

SOURCE = "retrorides"
BOARD = f"{BASE}/board/57/cars-sale-1985-older"


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
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(BOARD)
        resp.raise_for_status()
        return parse_page(resp.text, fx_day)
