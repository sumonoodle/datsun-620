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

# Round 4 (final Truck2Hand attempt): the API client wasn't in the page
# chunks, so it lives in a shared numbered chunk. Pull them all plus
# robots/sitemap; if the endpoint still doesn't surface, T2H is deferred.
_T2H = "https://www.truck2hand.com"
PAGES = [
    (f"t2h-shared-{name.split('-')[0].split('.')[0]}.js.gz",
     f"{_T2H}/_next/static/chunks/{name}")
    for name in [
        "2624-baaa5ab3dcbecf93.js", "3416-0c6ea0c94d93d0e6.js",
        "450-74657f62ba267987.js", "4900-311a696856e86804.js",
        "6069-063ef278331e6352.js", "6131.3ee8ac93c70fa06f.js",
        "7373-62308ce18f69d13f.js", "9034-0ce2cc1183b93086.js",
        "9250-69fca050068b7768.js", "9497-333959e68a8f6d6d.js",
        "9948-c0d3ef38e04e827f.js", "webpack-e7de7a0c643c1a66.js",
    ]
] + [
    ("t2h-robots.txt.gz", f"{_T2H}/robots.txt"),
    ("t2h-sitemap.xml.gz", f"{_T2H}/sitemap.xml"),
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
