"""Collector: Retro Rides forum (UK), the pre-1985 cars-for-sale board.

ProBoards, plain server-rendered HTML. Threads ARE the listings; titles
carry year, price and location by board convention ("1978 Datsun 620
Pickup long bed £8995 Sussex", "SOLD!" appended when gone). Research
found several real UK 620s a year here — the best UK niche source.
Thread id is the stable identity; price parsed from the title (£8995,
£8.9k both seen).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "retrorides"
BASE = "https://forum.retro-rides.org"
BOARDS = [f"{BASE}/board/57/cars-sale-1985-older", f"{BASE}/board/58/cars-sale"]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_THREAD_RE = re.compile(r"/thread/(\d+)/[^/'\"]*")
_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_OTHER_GEN_RE = re.compile(r"(?<!\d)(?:520|521|720)(?!\d)|D2[12]", re.I)
_DATSUN_RE = re.compile(r"datsun", re.I)
# £8995, £8,995, £8.9k
_GBP_RE = re.compile(r"£\s*([\d,]+(?:\.\d+)?)(k?)", re.I)


def _price(title: str) -> float | None:
    m = _GBP_RE.search(title)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return n * 1000 if m.group(2) else n


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
        # Board convention puts make in the title; both checks required so a
        # non-Datsun "620 miles" title cannot slip through.
        if not (_DATSUN_RE.search(title) and _620_RE.search(title)):
            continue
        if _OTHER_GEN_RE.search(title):
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
            "year": normalize.extract_year(title),
            "country": "GB",
            "region": None,
            "drive_side": normalize.infer_drive_side("GB", title),
            "king_cab": king_cab.check(title),
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
        print(f"retrorides: partial failure, continuing without {failures}")
    return records
