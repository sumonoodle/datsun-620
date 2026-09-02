"""Fetch real pages for the Asia round-2 sources (owner request: more
Thailand/Vietnam/Japan coverage).

Round 1: the Japan bench — export portals with Datsun Truck model
categories, all probed 200 in July but deferred as thin; the owner now
wants recall over thrift. Thai/Vietnamese candidates follow once the
research agent reports URL patterns. Same scaffolding lifecycle as
always: pages in, parsers built, scaffolding deleted.
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
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8,th;q=0.7,vi;q=0.7",
}

# Round 2: the Thai finds. Truck2Hand's July "fully client-side" verdict
# has aged out — Google now indexes its category and listing pages with
# LIVE 620s on them; Chobrod has a dedicated /car-datsun-620 tree.
PAGES = [
    ("truck2hand-datsun.html.gz",
     "https://www.truck2hand.com/category/cat_pickup+brand_brand-384-datsun/"),
    ("truck2hand-620.html.gz",
     "https://www.truck2hand.com/category/cat_pickup+brand_brand-384-datsun+model_620/"),
    ("truck2hand-listing.html.gz",
     "https://www.truck2hand.com/listing/Y9l6V20mlb/"),
    ("chobrod-620.html.gz",
     "https://chobrod.com/car-datsun-620"),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for name, url in PAGES:
            try:
                resp = client.get(url)
                print(f"{name}: HTTP {resp.status_code}, {len(resp.content)} bytes, "
                      f"final={resp.url}")
                if resp.status_code == 200:
                    (OUT_DIR / name).write_bytes(gzip.compress(resp.content, 9))
            except Exception as exc:
                print(f"{name}: {type(exc).__name__}: {exc}")
            time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
