"""Fetch real search-result pages from the Phase A/B Asian sources.

Runs on a GitHub runner (the sandbox has no general egress) and saves each
page gzipped under data/research/pages/, committed back to the dev branch.
The new collectors' parsers are written against THIS markup, then trimmed
copies become permanent test fixtures. Like the probe, this is scaffolding:
deleted once the collectors ship.
"""

from __future__ import annotations

import gzip
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "pages"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8,th;q=0.7",
}

DATSUN_TRUCK_JA = "ダットサントラック"
DATSUN_620_JA = "ダットサン 620"

PAGES = [
    ("goonet-exchange.html.gz",
     "https://www.goo-net-exchange.com/usedcars/NISSAN/DATSUN_TRUCK/"),
    ("carsensor.html.gz",
     f"https://www.carsensor.net/usedcar/freeword/{quote(DATSUN_TRUCK_JA)}/index.html"),
    ("yahoo-open-truck.html.gz",
     f"https://auctions.yahoo.co.jp/search/search?p={quote(DATSUN_TRUCK_JA)}"),
    ("yahoo-open-620.html.gz",
     f"https://auctions.yahoo.co.jp/search/search?p={quote(DATSUN_620_JA)}"),
    ("yahoo-closed-620.html.gz",
     f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={quote(DATSUN_620_JA)}"),
    ("truck2hand.html.gz",
     "https://www.truck2hand.com/search?keyword=" + quote("datsun 620")),
    ("kaidee.html.gz",
     "https://rod.kaidee.com/c12-auto-pickup?q=datsun"),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for name, url in PAGES:
            try:
                resp = client.get(url)
                print(f"{name}: HTTP {resp.status_code}, {len(resp.content)} bytes")
                if resp.status_code == 200:
                    (OUT_DIR / name).write_bytes(gzip.compress(resp.content, 9))
                else:
                    failures += 1
            except Exception as exc:
                print(f"{name}: {type(exc).__name__}: {exc}")
                failures += 1
            time.sleep(2)
    print(f"done, {failures} failure(s)")
    return 0  # partial results are still useful; the commit step picks up what saved


if __name__ == "__main__":
    sys.exit(main())
