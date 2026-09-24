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
PAGES = [
    # --- existing sources, Hilux equivalents ---
    ("bat-toyota.html", "existing", "https://bringatrailer.com/toyota/"),
    ("bat-toyota-pickup.html", "existing", "https://bringatrailer.com/toyota/pickup/"),
    ("bat-toyota-hilux.html", "existing", "https://bringatrailer.com/toyota/hilux/"),
    ("classiccars-pickup.html", "existing", "https://classiccars.com/listings/find/1978-1984/toyota/pickup"),
    ("classiccars-hilux.html", "existing", "https://classiccars.com/listings/find/all-years/toyota/hilux"),
    ("hemmings-pickup.html", "existing", "https://www.hemmings.com/classifieds/cars-for-sale/toyota/pickup"),
    ("carsandbids-search.html", "existing", "https://carsandbids.com/search/toyota%20pickup"),
    ("goonet-exchange-hilux.html", "existing", "https://www.goo-net-exchange.com/usedcars/TOYOTA/HILUX/"),
    ("carsensor-hilux.html", "existing", f"https://www.carsensor.net/usedcar/freeword/{HILUX_JP}/index.html"),
    ("yahoo-open-hilux.html", "existing", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP}&auccat=26360"),
    ("yahoo-open-rn30.html", "existing", f"https://auctions.yahoo.co.jp/search/search?p={HILUX_JP}+RN30"),
    ("yahoo-closed-hilux.html", "existing", f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={HILUX_JP}+RN30"),
    ("kaidee-hilux.html", "existing", "https://rod.kaidee.com/c11-auto-car?q=hilux"),
    ("kaidee-hilux-th.html", "existing", f"https://rod.kaidee.com/c11-auto-car?q={HILUX_TH}"),
    ("truck2hand-pickup.html", "existing", "https://www.truck2hand.com/category/cat_pickup/"),
    ("truck2hand-search.html", "existing", "https://www.truck2hand.com/search?q=hilux"),
    ("kijiji-pickup.html", "existing", "https://www.kijiji.ca/b-canada/toyota-pickup-1981/k0l0"),
    ("kijiji-hilux.html", "existing", "https://www.kijiji.ca/b-canada/toyota-hilux/k0l0"),
    ("barnfinds-pickup-feed.xml", "existing", "https://barnfinds.com/tag/toyota-pickup/feed/"),
    ("barnfinds-hilux-feed.xml", "existing", "https://barnfinds.com/tag/toyota-hilux/feed/"),
    ("barnfinds-toyota-feed.xml", "existing", "https://barnfinds.com/tag/toyota/feed/"),
    ("flex-hilux.html", "existing", f"https://www.flexnet.co.jp/search/freeword/{HILUX_JP}"),
    ("kuruma-ex-toyota.html", "existing", "https://kuruma-ex.jp/usedcar/search/result/maker/TO"),
    ("everycar-toyota.html", "existing", "https://www.everycar.jp/used-cars?make=toyota"),
    ("pistonheads-hilux.html", "existing", "https://www.pistonheads.com/buy/toyota/hilux"),
    ("pistonheads-toyota.html", "existing", "https://www.pistonheads.com/buy/toyota"),
    ("retrorides-board57.html", "existing", "https://forum.retro-rides.org/board/57/cars-sale-1985-older"),
    ("trovit-us-hilux.html", "existing", "https://cars.trovit.com/used-cars/toyota-hilux"),
    ("trovit-us-pickup.html", "existing", "https://cars.trovit.com/used-cars/toyota-pickup"),
    ("trovit-de-hilux.html", "existing", "https://de.trovit.com/autos/gebrauchtwagen/toyota-hilux"),
    ("trovit-uk-hilux.html", "new", "https://cars.trovit.co.uk/used-cars/toyota-hilux"),
    ("trovit-au-hilux.html", "new", "https://cars.trovit.com.au/used-cars/toyota-hilux"),
    ("trovit-za-hilux.html", "new", "https://cars.trovit.co.za/used-cars/toyota-hilux"),
    ("kleinanzeigen-hilux.html", "existing", "https://www.kleinanzeigen.de/s-autos/hilux/k0c216"),
    # --- new: UK ---
    ("carandclassic-search.html", "new", "https://www.carandclassic.com/search?q=toyota+hilux"),
    ("carandclassic-cat.html", "new", "https://www.carandclassic.com/cat/3/99/hilux/"),
    ("gumtree-uk-hilux.html", "new", "https://www.gumtree.com/cars-vans-motorbikes/uk/srpsearch+toyota+hilux"),
    ("autotrader-uk-hilux.html", "new", "https://www.autotrader.co.uk/car-search?make=Toyota&model=Hilux&postcode=SP47DE&year-to=1985"),
    ("classictrader-hilux.html", "new", "https://www.classic-trader.com/uk/cars/search/toyota/hilux"),
    ("classiccarsforsale-uk-hilux.html", "new", "https://www.classiccarsforsale.co.uk/toyota/hilux"),
    ("ebay-uk-web.html", "new", "https://www.ebay.co.uk/sch/i.html?_nkw=toyota+hilux+rn30&_sacat=9801"),
    # --- new: Australia / NZ ---
    ("gumtree-au-hilux.html", "new", "https://www.gumtree.com.au/s-cars-vans-utes/toyota/hilux/c18320"),
    ("carsales-hilux.html", "new", "https://www.carsales.com.au/cars/toyota/hilux/"),
    ("tradeuniquecars-hilux.html", "new", "https://www.tradeuniquecars.com.au/search/make-toyota/model-hilux"),
    ("carsguide-hilux.html", "new", "https://www.carsguide.com.au/buy-a-car/toyota/hilux"),
    ("justcars-hilux.html", "new", "https://www.justcars.com.au/cars-for-sale/toyota/hilux"),
    ("trademe-hilux.html", "new", "https://www.trademe.co.nz/a/motors/cars/toyota/hilux"),
    ("trademe-api-hilux.json", "new", "https://api.trademe.co.nz/v1/Search/Motors/Used.json?make=Toyota&model=Hilux&year_max=1984"),
    # --- new: US / Canada ---
    ("autotrader-classics-pickup.html", "new", "https://classics.autotrader.com/classic-cars-for-sale/toyota-pickup-for-sale"),
    ("cars-com-pickup.html", "new", "https://www.cars.com/shopping/results/?makes[]=toyota&models[]=toyota-pickup&year_max=1984&stock_type=used"),
    ("gateway-pickup.html", "new", "https://www.gatewayclassiccars.com/quick/Toyota+Pickup"),
    ("craigslist-la.html", "new", "https://losangeles.craigslist.org/search/cta?query=toyota+pickup&max_auto_year=1984&min_auto_year=1978"),
    ("craigslist-sfbay.html", "new", "https://sfbay.craigslist.org/search/cta?query=toyota+pickup&max_auto_year=1984&min_auto_year=1978"),
    ("hagerty-toyota.html", "new", "https://www.hagerty.com/marketplace/search?make=Toyota&model=Pickup"),
    ("mecum-toyota.html", "new", "https://www.mecum.com/lots/?search=toyota%20pickup"),
    ("ih8mud-classifieds.html", "new", "https://forum.ih8mud.com/forums/vehicles-for-sale.121/"),
    ("yotatech-classifieds.html", "new", "https://www.yotatech.com/forums/f68/"),
    # --- new: Japan / Asia ---
    ("goonet-jp-hilux.html", "new", "https://www.goo-net.com/usedcar/brand-TOYOTA/car-HILUX/"),
    ("one2car-hilux.html", "new", "https://www.one2car.com/en/cars-for-sale/toyota/hilux?year_max=1984"),
    ("carfromjapan-hilux.html", "new", "https://carfromjapan.com/cheap-used-toyota-hilux-for-sale"),
    ("beforward-hilux.html", "new", "https://www.beforward.jp/stocklist/make=1/model=1224/sortkey=n"),
    ("tcv-hilux.html", "new", "https://www.tc-v.com/used_car/toyota/hilux/"),
    # --- new: South Africa / Europe ---
    ("autotrader-za-hilux.html", "new", "https://www.autotrader.co.za/cars-for-sale/toyota/hilux?year=1978-to-1984"),
    ("gumtree-za-hilux.html", "new", "https://www.gumtree.co.za/s-cars-bakkies/toyota+hilux/v1c9077q0p1"),
    ("marktplaats-hilux.html", "new", "https://www.marktplaats.nl/q/toyota+hilux/"),
    ("donedeal-hilux.html", "new", "https://www.donedeal.ie/cars/Toyota/Hilux"),
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
                    resp = client.get(url)
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
