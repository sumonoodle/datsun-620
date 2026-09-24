"""Fetch real Hilux (3rd gen, 1978-83) search pages for the Hilux expansion.

Runner-side, same lifecycle as every earlier research round: gzipped pages
land in data/research/pages-hilux/ on the dev branch, parsers get written
against them, and this scaffolding is deleted once the collectors ship.

Same posture as the 2026-09-20 round: robots.txt is obeyed via
urllib.robotparser and a disallowed URL is skipped, not fetched. No
evasion. A non-200 prints its status and saves nothing, so the fetch
doubles as a reachability probe. The summary lands in probe.json.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "pages-hilux"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-GB,en;q=0.9",
}
HILUX_JP = quote("ハイラックス")
HILUX_TH = quote("ไฮลักซ์")

# (file name, group, url). Group: "existing" = a source already scraped
# for the 620; "new" = a candidate source for the Hilux.
# Round 2 (2026-09-24): the pages the collector agents asked for after
# building against round 1: year-capped and model-scoped variants, page-2
# URL formats, and the Yahoo queries built exactly as the collector does.
HILUX_JP_Q = quote("ハイラックス")
PAGES = [
    # Round 4: can Gumtree UK be filtered without /search (robots-disallowed)?
    ("gumtree-uk-path-date.html", "r4", "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux?sort=date"),
    ("gumtree-uk-path-petrol.html", "r4", "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux?vehicle_fuel_type=petrol"),
    ("gumtree-uk-rn30.html", "r4", "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux+rn30"),
    ("gumtree-uk-classic.html", "r4", "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux+classic"),
    ("marktplaats-hilux-p2.html", "r4", "https://www.marktplaats.nl/l/auto-s/q/toyota+hilux/p/2/"),
    ("kuruma-ex-s112-1989.html", "r4", "https://kuruma-ex.jp/usedcar/search/result/maker/TO/shashu/S112/year_max/1989"),
]


def _robots_ok(client: httpx.Client, url: str, cache: dict) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = client.get(origin + "/robots.txt")
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        cache[origin] = rp
    return cache[origin].can_fetch(HEADERS["User-Agent"], url)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    robots: dict = {}
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for name, group, url in PAGES:
            entry = {"file": name, "group": group, "url": url}
            try:
                if not _robots_ok(client, url, robots):
                    entry["status"] = "robots-disallowed"
                else:
                    jp = any(d in url for d in (".jp/", ".co.jp", "carsensor.net"))
                    resp = client.get(url, headers={"Accept-Language": "ja,en;q=0.5"} if jp else None)
                    body = resp.content
                    low = body.lower()
                    entry.update({
                        "status": resp.status_code,
                        "final_url": str(resp.url),
                        "bytes": len(body),
                        "mentions_hilux": b"hilux" in low or "ハイラックス".encode() in body,
                        "js_required": b"javascript required" in low or b"enable javascript" in low,
                    })
                    if resp.status_code == 200:
                        (OUT_DIR / (name + ".gz")).write_bytes(gzip.compress(body, 9))
            except Exception as exc:
                entry["status"] = f"{type(exc).__name__}: {exc}"[:200]
            print(json.dumps(entry, ensure_ascii=False))
            results.append(entry)
            time.sleep(2)
    (OUT_DIR / "probe.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
