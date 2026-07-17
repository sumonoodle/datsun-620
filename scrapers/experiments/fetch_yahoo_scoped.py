"""One-off: verify Yahoo Auctions' whole-vehicle category id (26360).

The all-620s policy leans on category-scoped open searches to keep toys and
parts out. 26360 (中古車・新車) came from research, not observation — this
fetches the scoped searches so the id is proven against real pages before
the collector trusts it. Scaffolding, deleted after use.
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
    "Accept-Language": "ja,en;q=0.8",
}

PAGES = [
    ("yahoo-scoped-620.html.gz",
     "https://auctions.yahoo.co.jp/search/search?p=" + quote("ダットサン 620") + "&auccat=26360"),
    ("yahoo-scoped-truck.html.gz",
     "https://auctions.yahoo.co.jp/search/search?p=" + quote("ダットサントラック") + "&auccat=26360"),
    ("yahoo-cat-26360.html.gz",
     "https://auctions.yahoo.co.jp/category/list/26360/"),
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
