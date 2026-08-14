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

PAGES = [
    ("pistonheads-datsun.html.gz",
     "https://www.pistonheads.com/buy/datsun"),
    ("pistonheads-other.html.gz",
     "https://www.pistonheads.com/buy/datsun/other-models"),
    ("ccfs-620.html.gz",
     "https://www.classiccarsforsale.co.uk/datsun/620"),
    ("ccfs-datsun.html.gz",
     "https://www.classiccarsforsale.co.uk/datsun"),
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
