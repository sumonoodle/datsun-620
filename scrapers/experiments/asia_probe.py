"""Reachability probe for candidate Asian listing sources.

Runs from a GitHub Actions runner (NOT the sandbox, which has no general
egress) and records, for every candidate site, whether the homepage and a
representative search URL answer to a plain HTTPS client from GitHub's IP
space. This is the evidence for the free-vs-paid-proxy decision: a site that
200s here can be scraped like Bring a Trailer; a site that 403s here needs
Playwright, a proxy, or its own saved-search email alerts instead.

Each site gets TWO probes (root + search) so a wrong guess at the search URL
shape (404) is distinguishable from an IP block (403/503 on everything).

Output: data/research/asia-probe.json. Statuses only, no page content is
stored beyond a boolean "does the body mention datsun".
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[2] / "data" / "research" / "asia-probe.json"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.8,th;q=0.7",
}

# (key, region, root URL, search/category URL). Search URLs came from the
# desk research pass; some are best guesses and may 404, which is why the
# root is probed separately.
SITES = [
    # Japan: export-facing
    ("goo-net-exchange", "JP export", "https://www.goo-net-exchange.com/",
     "https://www.goo-net-exchange.com/usedcars/NISSAN/DATSUN_TRUCK/"),
    ("tcv", "JP export", "https://www.tc-v.com/",
     "https://www.tc-v.com/used_car/nissan/datsun%20pickup/"),
    ("carfromjapan", "JP export", "https://carfromjapan.com/",
     "https://carfromjapan.com/cheap-used-nissan-datsun-pickup-for-sale"),
    ("jdmexport", "JP export", "https://www.jdmexport.com/",
     "https://www.jdmexport.com/nissan-datsun-pickup-for-sale"),
    ("beforward", "JP export", "https://www.beforward.jp/",
     "https://www.beforward.jp/stocklist/make=3/model=386"),
    ("sbtjapan", "JP export", "https://www.sbtjapan.com/",
     "https://www.sbtjapan.com/used-cars/nissan/datsun-truck/"),
    ("japan-partner", "JP export", "https://www.japan-partner.com/",
     "https://www.japan-partner.com/auction/Nissan/DATSUN+TRUCK/cars-for-sale.html"),
    ("japanesecartrade", "JP export", "https://www.japanesecartrade.com/",
     "https://www.japanesecartrade.com/stock_list.php?make_id=8&model_str=DATSUN%20TRUCK"),
    # Japan: domestic
    ("carsensor", "JP domestic", "https://www.carsensor.net/",
     "https://www.carsensor.net/usedcar/freeword/%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3%E3%83%88%E3%83%A9%E3%83%83%E3%82%AF/index.html"),
    ("goo-net", "JP domestic", "https://www.goo-net.com/",
     "https://www.goo-net.com/usedcar/brand-NISSAN/car-DATSUN_TRUCK/"),
    ("yahoo-auctions", "JP domestic", "https://auctions.yahoo.co.jp/",
     "https://auctions.yahoo.co.jp/search/search?p=%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3%E3%83%88%E3%83%A9%E3%83%83%E3%82%AF%20620"),
    ("yahoo-closed", "JP domestic", "https://auctions.yahoo.co.jp/",
     "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3%20620"),
    ("jimoty", "JP domestic", "https://jmty.jp/",
     "https://jmty.jp/all/car-kw-%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3%E3%83%88%E3%83%A9%E3%83%83%E3%82%AF"),
    ("rockyauto", "JP dealer", "https://www.rockyauto.co.jp/",
     "https://www.rockyauto.co.jp/stock/"),
    ("japan-vintage", "JP dealer", "https://japan-vintage.com/",
     "https://japan-vintage.com/stocklist/"),
    ("nosweb", "JP dealer", "https://ucar.nosweb.jp/",
     "https://ucar.nosweb.jp/searchlist.html?mk=3&md=29"),
    # Thailand
    ("truck2hand", "TH", "https://www.truck2hand.com/",
     "https://www.truck2hand.com/search?keyword=datsun%20620"),
    ("kaidee", "TH", "https://www.kaidee.com/",
     "https://rod.kaidee.com/c12-auto-pickup?q=datsun"),
    ("one2car", "TH", "https://www.one2car.com/",
     "https://www.one2car.com/en/cars-for-sale/datsun/620"),
    ("chobrod", "TH", "https://www.chobrod.com/",
     "https://www.chobrod.com/car-datsun-620-pickup/"),
    ("bahtsold", "TH", "https://www.bahtsold.com/",
     "https://www.bahtsold.com/search/result?search_text=datsun"),
    # Malaysia / Indonesia
    ("mudah", "MY", "https://www.mudah.my/",
     "https://www.mudah.my/malaysia/cars-for-sale/datsun"),
    ("carlist", "MY", "https://www.carlist.my/",
     "https://www.carlist.my/cars/datsun"),
    ("carmudi-id", "ID", "https://www.carmudi.co.id/",
     "https://www.carmudi.co.id/mobil-dijual/datsun/"),
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
        for key, region, root, search in SITES:
            entry = {"site": key, "region": region,
                     "root": probe(client, root),
                     "search": probe(client, search)}
            results.append(entry)
            r, s = entry["root"], entry["search"]
            print(f"{key:20s} root={r.get('status')} search={s.get('status')} "
                  f"datsun={s.get('mentions_datsun')}")
            time.sleep(1)  # politeness gap
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"date": date.today().isoformat(), "results": results},
                              indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
