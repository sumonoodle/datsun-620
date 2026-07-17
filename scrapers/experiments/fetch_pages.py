"""Fetch real search pages for the deep-dive collectors.

Runner-side (the sandbox has no egress); pages land gzipped in
data/research/pages/ on this branch, parsers get written against them,
trimmed copies become fixtures, then this scaffolding is deleted — the
same lifecycle as the Asia rounds.
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
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8,es;q=0.7",
}

PAGES = [
    ("classiccars.html.gz",
     "https://classiccars.com/listings/find/all-years/datsun/620"),
    ("kijiji.html.gz",
     "https://www.kijiji.ca/b-canada/datsun-620/k0l0"),
    ("barnfinds-feed.xml.gz",
     "https://barnfinds.com/tag/datsun-620/feed/"),
    ("barnfinds-tag.html.gz",
     "https://barnfinds.com/tag/datsun-620/"),
    ("flex.html.gz",
     "https://www.flexnet.co.jp/search/freeword/" + quote("ダットサン")),
    ("kuruma-ex.html.gz",
     "https://kuruma-ex.jp/usedcar/search/result/maker/NI/shashu/S061"),
    ("mercadolibre.html.gz",
     "https://listado.mercadolibre.com.mx/datsun-620"),
    ("justcars.html.gz",
     "https://www.justcars.com.au/cars-for-sale/search?taxonomy%5B0%5D%5B0%5D=datsun"),
    ("tokyocarz.html.gz",
     "https://www.tokyocarz.com/listop/cheap-used-nissan-datsun-for-sale"),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
