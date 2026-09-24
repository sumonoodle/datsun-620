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
    ("kijiji-cars-pickup.html", "r2", "https://www.kijiji.ca/b-cars-trucks/canada/toyota-pickup/k0c174l0"),
    ("kijiji-cars-hilux.html", "r2", "https://www.kijiji.ca/b-cars-trucks/canada/toyota-hilux/k0c174l0"),
    ("kijiji-classic-toyota.html", "r2", "https://www.kijiji.ca/b-classic-cars/canada/toyota/k0c122l0"),
    ("pistonheads-hilux-yearto.html", "r2", "https://www.pistonheads.com/buy/toyota/hilux?yearTo=1984"),
    ("pistonheads-classifieds-m586.html", "r2", "https://www.pistonheads.com/classifieds?Category=used-cars&M=586&YearTo=1984&ResultsPerPage=16"),
    ("pistonheads-classifieds-toyota.html", "r2", "https://www.pistonheads.com/classifieds?Category=used-cars&MakeId=51&YearTo=1984"),
    ("trovit-uk-hilux-maxyear.html", "r2", "https://cars.trovit.co.uk/used-cars/toyota-hilux?max_year=1984"),
    ("kleinanzeigen-hilux-ez.html", "r2", "https://www.kleinanzeigen.de/s-autos/hilux/k0c216+autos.ez_i:1978,1984"),
    ("kleinanzeigen-hilux-p2.html", "r2", "https://www.kleinanzeigen.de/s-autos/seite:2/hilux/k0c216"),
    ("goonet-exchange-hilux-pickup.html", "r2", "https://www.goo-net-exchange.com/usedcars/TOYOTA/HILUX_PICK_UP/"),
    ("carsensor-hilux-ymax.html", "r2", f"https://www.carsensor.net/usedcar/freeword/{HILUX_JP_Q}/index.html?YMAX=1989"),
    ("carsensor-model-ymax.html", "r2", "https://www.carsensor.net/usedcar/bTO/s112/index.html?YMAX=1989"),
    ("yahoo-rn30.html", "r2", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP_Q}%20RN30"),
    ("yahoo-12r.html", "r2", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP_Q}%2012R"),
    ("yahoo-kyusha-cat.html", "r2", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP_Q}%20{quote('旧車')}&auccat=26360"),
    ("yahoo-showa-cat.html", "r2", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP_Q}%20{quote('昭和')}&auccat=26360"),
    ("flex-hilux-sort4.html", "r2", f"https://www.flexnet.co.jp/search/freeword/{HILUX_JP_Q}?sort=4"),
    ("kuruma-ex-s112-capped.html", "r2", "https://kuruma-ex.jp/usedcar/search/result/maker/TO/shashu/S112?year_max=1984"),
    ("kuruma-ex-s112.html", "r2", "https://kuruma-ex.jp/usedcar/search/result/maker/TO/shashu/S112"),
    ("everycar-hilux.html", "r2", "https://www.everycar.jp/used-cars?make=toyota&model=hilux"),
    ("everycar-hilux-p2.html", "r2", "https://www.everycar.jp/used-cars?page=2&make=toyota&model=hilux"),
    ("truck2hand-hilux-p2.html", "r2", "https://www.truck2hand.com/search/?q=hilux&page=2"),
    ("truck2hand-hilux-th.html", "r2", f"https://www.truck2hand.com/search/?q={quote('ไฮลักซ์')}"),
    ("kaidee-robots.txt", "r2", "https://www.kaidee.com/robots.txt"),
    ("kaidee-api.js", "r2", "https://www.kaidee.com/assets/api-JDpYZ1q3.js"),
    # Round 3: the new-source agent's filter/sort URLs.
    ("gumtree-uk-petrol-date.html", "r3", "https://www.gumtree.com/search?search_category=cars-vans-motorbikes&search_location=uk&q=toyota+hilux&vehicle_fuel_type=petrol&sort=date"),
    ("gumtree-uk-date.html", "r3", "https://www.gumtree.com/search?search_category=cars-vans-motorbikes&search_location=uk&q=toyota+hilux&sort=date"),
    ("gumtree-za-petrol.html", "r3", "https://www.gumtree.co.za/s-cars-bakkies/toyota~hilux~petrol/v1c9077a3mamofup1"),
    ("gumtree-za-petrol-p2.html", "r3", "https://www.gumtree.co.za/s-cars-bakkies/toyota~hilux~petrol/page-2/v1c9077a3mamofup2"),
    ("tcv-hilux-years.html", "r3", "https://www.tc-v.com/used_car/toyota/hilux/?fid=1978&jid=1984"),
    ("carfromjapan-oldest.html", "r3", "https://carfromjapan.com/cheap-used-toyota-hilux-for-sale?sortBy=registrationDate"),
    ("carfromjapan-maxyear.html", "r3", "https://carfromjapan.com/cheap-used-toyota-hilux-for-sale?maxYear=1985"),
    ("goonet-jp-other.html", "r3", "https://www.goo-net.com/usedcar/brand-TOYOTA/car-HILUX/model--1-10104114/"),
    ("goonet-jp-pickup.html", "r3", "https://www.goo-net.com/usedcar/brand-TOYOTA/car-HILUX_PICK_UP/"),
    ("classictrader-toyota.html", "r3", "https://www.classic-trader.com/uk/cars/search/toyota"),
    ("marktplaats-autos-hilux.html", "r3", "https://www.marktplaats.nl/l/auto-s/q/toyota+hilux/"),
    ("marktplaats-oldtimers-toyota.html", "r3", "https://www.marktplaats.nl/l/auto-s/oldtimers/q/toyota/"),
    ("marktplaats-toyota-hilux.html", "r3", "https://www.marktplaats.nl/l/auto-s/toyota/q/hilux/"),
    ("hagerty-toyota-make.html", "r3", "https://www.hagerty.com/marketplace/search?make=Toyota"),
    ("hagerty-toyota-truck.html", "r3", "https://www.hagerty.com/marketplace/search?make=Toyota&model=Truck"),
    ("ih8mud-home.html", "r3", "https://forum.ih8mud.com/"),
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
