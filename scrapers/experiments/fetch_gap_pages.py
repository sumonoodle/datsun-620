"""Fetch real pages for the gap-sweep sources (PistonHeads first).

Runner-side, same lifecycle as every earlier round: gzipped pages land in
data/research/pages/ on this branch, parsers get written against them,
scaffolding deleted after. The candidate list grows as the sweep's
research agents report; push updates to this file to fetch more.
"""

from __future__ import annotations

import gzip
import sys
import time
from pathlib import Path

import httpx

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "pages"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-GB,en;q=0.9",
}

# Round 2: the sweep agents' candidates. Fetch doubles as reachability
# probe — non-200s print their status and save nothing.
PAGES = [
    ("ratsun-classifieds.html.gz",
     "https://ratsun.net/classifieds/category/5-datsun-vehicles/"),
    ("nicoclub-classifieds.html.gz",
     "https://forums.nicoclub.com/datsun-classified-ads.html"),
    ("retrorides-board57.html.gz",
     "https://forum.retro-rides.org/board/57/cars-sale-1985-older"),
    ("donedeal-datsun.html.gz",
     "https://www.donedeal.ie/all?words=datsun"),
    ("honestjohn-pickups.html.gz",
     "https://classics.honestjohn.co.uk/cars-for-sale/search/Datsun/shape-Pickup/?type=For+Sale"),
    ("gumtree-datsun.html.gz",
     "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+datsun"),
    ("trovit-620.html.gz",
     "https://cars.trovit.com/used-cars/datsun-620"),
    ("gateway-620.html.gz",
     "https://www.gatewayclassiccars.com/quick/Datsun+620"),
    ("tradeuniquecars.html.gz",
     "https://www.tradeuniquecars.com.au/search/make-datsun"),
    ("carsguide-620ute.html.gz",
     "https://www.carsguide.com.au/buy-a-car/datsun/620/ute"),
    ("kleinanzeigen-pickup.html.gz",
     "https://www.kleinanzeigen.de/s-autos/datsun-pickup/k0c216"),
    ("classictrader-620.html.gz",
     "https://www.classic-trader.com/uk/cars/search/datsun/620"),
    ("my105-datsun.html.gz",
     "https://www.my105.com/cars/datsun-for-sale"),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for name, url in PAGES:
            try:
                resp = client.get(url)
                print(f"{name}: HTTP {resp.status_code}, {len(resp.content)} bytes")
                if resp.status_code == 200:
                    (OUT_DIR / name).write_bytes(gzip.compress(resp.content, 9))
            except Exception as exc:
                print(f"{name}: {type(exc).__name__}: {exc}")
            time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
