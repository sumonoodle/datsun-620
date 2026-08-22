"""Fetch Trovit country editions + the deferred Hagerty markup check.

Trovit US shipped in the gap sweep; if the country editions share its
markup, one parser covers the UK/DE/ES/AU tails — including listings from
bot-walled sites (leboncoin, Marktplaats, Milanuncios) that syndicate to
Trovit. Hagerty answered 200 in the deep-dive probe but looked
JS-rendered; this settles it. Scaffolding, deleted after use.
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
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.8,es;q=0.7",
}

PAGES = [
    # Round 2: de.trovit.com/autos/gebrauchtwagen worked, so the canonical
    # shape is {cc}.trovit.com/{localized-vertical}/{query}. Correcting the
    # UK/ES/AU guesses to that shape.
    ("trovit-uk.html.gz", "https://uk.trovit.com/cars/used-cars/datsun-620"),
    ("trovit-es.html.gz", "https://es.trovit.com/coches/coches/datsun-620"),
    ("trovit-au.html.gz", "https://au.trovit.com/cars/used-cars/datsun-620"),
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
