"""Reachability probe, round 2: the deep-dive source candidates.

Same method as the retired asia_probe.py (results in
data/research/asia-probe.json): from a GitHub runner, hit each candidate's
root AND its 620/Datsun search URL, record status/bytes/datsun-mention, so
a wrong URL guess (404) is distinguishable from an IP block (403).
Candidates come from the four-agent deep research pass, filtered to sites
worth scraping directly (aggregators, classifieds, dealer stock pages).
Scaffolding: deleted once the integration decision is made.

Output: data/research/deep-probe.json.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[2] / "data" / "research" / "deep-probe.json"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8",
}

SITES = [
    # Aggregators (highest leverage)
    ("classic-com", "aggregator", "https://www.classic.com/",
     "https://www.classic.com/m/nissan/truck/620/"),
    ("glenmarch", "aggregator", "https://www.glenmarch.com/",
     "https://www.glenmarch.com/cars/results/quick/Datsun/620"),
    ("barnfinds", "aggregator", "https://barnfinds.com/",
     "https://barnfinds.com/tag/datsun-620/"),
    ("theparking", "aggregator", "https://www.theparking-cars.com/",
     "https://www.theparking-cars.com/used-cars/datsun-pick-up.html"),
    ("classicdriver", "aggregator", "https://www.classicdriver.com/",
     "https://www.classicdriver.com/en/cars/datsun/620"),
    ("ccfs-uk", "aggregator", "https://www.classiccarsforsale.co.uk/",
     "https://www.classiccarsforsale.co.uk/datsun/620"),
    # US/UK/global classifieds & marketplaces
    ("carandclassic", "classifieds", "https://www.carandclassic.com/",
     "https://www.carandclassic.com/list/68/620/"),
    ("classiccars-com", "classifieds", "https://classiccars.com/",
     "https://classiccars.com/listings/find/all-years/datsun/620"),
    ("autotrader-classics", "classifieds", "https://classics.autotrader.com/",
     "https://classics.autotrader.com/classic-cars-for-sale/datsun-620-for-sale"),
    ("hagerty", "classifieds", "https://www.hagerty.com/",
     "https://www.hagerty.com/marketplace/search?q=datsun%20620"),
    ("kijiji", "classifieds", "https://www.kijiji.ca/",
     "https://www.kijiji.ca/b-canada/datsun-620/k0l0"),
    ("mercadolibre-mx", "classifieds", "https://www.mercadolibre.com.mx/",
     "https://listado.mercadolibre.com.mx/datsun-620"),
    ("gumtree-au", "classifieds", "https://www.gumtree.com.au/",
     "https://www.gumtree.com.au/s-automotive/datsun+620/k0c9299"),
    ("trademe", "classifieds", "https://www.trademe.co.nz/",
     "https://www.trademe.co.nz/a/motors/search?search_string=datsun%20620"),
    ("carsales-au", "classifieds", "https://www.carsales.com.au/",
     "https://www.carsales.com.au/cars/datsun/620/ute-bodystyle/"),
    ("justcars-au", "classifieds", "https://www.justcars.com.au/",
     "https://www.justcars.com.au/cars-for-sale/search?taxonomy%5B0%5D%5B0%5D=datsun"),
    ("craigslist-la", "classifieds", "https://losangeles.craigslist.org/",
     "https://losangeles.craigslist.org/search/cta?query=datsun+620"),
    # JDM importer dealers (US) with real 620 history
    ("duncanimports", "dealer", "https://www.duncanimports.com/",
     "https://www.duncanimports.com/jdm-inventory.htm"),
    ("japaneseclassics", "dealer", "https://www.japaneseclassics.com/",
     "https://www.japaneseclassics.com/shop-cars/"),
    ("toprank-us", "dealer", "https://www.importavehicle.com/",
     "https://www.importavehicle.com/vehicles"),
    ("jdm-expo", "dealer", "https://jdm-expo.com/",
     "https://jdm-expo.com/11-nissan"),
    ("tokyocarz", "dealer", "https://www.tokyocarz.com/",
     "https://www.tokyocarz.com/listop/cheap-used-nissan-datsun-for-sale"),
    # Japan: auction-layer & sold-data
    ("aucfree", "jp-sold-data", "https://aucfree.com/",
     "https://aucfree.com/search?q=%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3%20620"),
    ("aleado", "jp-auction", "https://yahoo.aleado.com/",
     "https://yahoo.aleado.com/26360-catlist.html"),
    ("ts-export", "jp-auction", "https://www.ts-export.com/",
     "https://www.ts-export.com/page.php?page=about_classic_nissan_cars"),
    ("jpauc", "jp-auction", "https://jpauc.com/",
     "https://jpauc.com/auction/past"),
    ("aaajapan", "jp-auction", "https://aaajapan.com/",
     "https://aaajapan.com/auctions"),
    # Japan: domestic classic dealers & portals
    ("flex-kyusha", "jp-dealer", "https://www.flexnet.co.jp/",
     "https://www.flexnet.co.jp/search/freeword/%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3"),
    ("kuruma-ex", "jp-portal", "https://kuruma-ex.jp/",
     "https://kuruma-ex.jp/usedcar/search/result/maker/NI/shashu/S061"),
    ("carview", "jp-portal", "https://ucar.carview.yahoo.co.jp/",
     "https://ucar.carview.yahoo.co.jp/model/nissan/datsun/"),
    ("kurumaerabi", "jp-portal", "https://www.kurumaerabi.com/",
     "https://www.kurumaerabi.com/usedcar/nissan/926-2659/"),
    ("kakaku-used", "jp-portal", "https://kakaku.com/",
     "https://kakaku.com/kuruma/used/spec/Maker=3/Model=30345/"),
    ("webcartop", "jp-portal", "https://www.webcartop.jp/",
     "https://www.webcartop.jp/usedcar-search/?brand_cd=1015&car_cd=10154614"),
    # JP export portals with Datsun Truck model categories
    ("picknbuy24", "jp-export", "https://www.picknbuy24.com/",
     "https://www.picknbuy24.com/usedcar/?maker=nissan&model=datsun+truck"),
    ("cardealpage", "jp-export", "https://www.cardealpage.com/",
     "https://www.cardealpage.com/nissan/datsun%20truck/"),
    ("everycar", "jp-export", "https://www.everycar.jp/",
     "https://www.everycar.jp/nissan/datsun/"),
    ("satjapan", "jp-export", "https://satjapan.com/",
     "https://satjapan.com/used-cars/mk_nissan/md_datsun-pickup"),
    ("nikkyo", "jp-export", "https://www.nikkyocars.com/",
     "https://www.nikkyocars.com/m/stock/?maker=NISSAN&cars=DATSUN+PICKUP"),
    ("carused", "jp-export", "https://carused.jp/",
     "https://carused.jp/car-list/nissan/datsun-pickup"),
    ("carjunction", "jp-export", "https://www.carjunction.com/",
     "https://www.carjunction.com/category/trucks.html"),
]


def probe(client: httpx.Client, url: str) -> dict:
    t0 = time.monotonic()
    try:
        resp = client.get(url)
        body = resp.text[:200_000].lower()
        return {
            "url": url,
            "status": resp.status_code,
            "final_url": str(resp.url),
            "bytes": len(resp.content),
            "mentions_datsun": ("datsun" in body) or ("ダットサン" in body),
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }
    except Exception as exc:
        return {
            "url": url,
            "status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }


def main() -> int:
    results = []
    with httpx.Client(timeout=25, headers=HEADERS, follow_redirects=True) as client:
        for key, group, root, search in SITES:
            entry = {"site": key, "group": group,
                     "root": probe(client, root),
                     "search": probe(client, search)}
            results.append(entry)
            r, s = entry["root"], entry["search"]
            print(f"{key:22s} root={r.get('status')} search={s.get('status')} "
                  f"datsun={s.get('mentions_datsun')} bytes={s.get('bytes')}")
            time.sleep(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"date": date.today().isoformat(), "results": results},
                              indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
