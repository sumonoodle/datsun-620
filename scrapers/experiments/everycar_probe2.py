"""Probe round 2: what is everycar.jp's Datsun Truck model slug now?

Round 1 narrowed it sharply:
  - used-cars.php?make=nissan            -> 200, 25 cards  (the route lives)
  - used-cars.php?make=nissan&model=datsun-truck -> 404    (the SLUG died)
  - the homepage carries a NEW search form posting to /used-cars
    (extensionless) with make/model/min_year/max_year/...
  - robots.txt disallows ?keyword=, ?page=, ?sort=, ?ipp= — so keyword
    search and pagination are off limits; the model facet is the only
    polite way in, which makes finding its current slug the whole job.

So ask the site itself rather than guessing: the Nissan results page
renders a <select name="model"> listing every valid slug for that make.
This round prints it, walks the make index, learns the current detail-URL
shape from real cards, and then tries the surviving candidates on both
the .php and extensionless routes.

Scaffolding: delete once the collector is fixed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings.everycar import HEADERS

BASE = "https://www.everycar.jp"


def get(client, url):
    try:
        return client.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    except Exception as exc:
        print(f"    {type(exc).__name__}: {str(exc)[:110]}")
        return None


def main() -> int:
    with httpx.Client() as client:
        print("=== A. valid model slugs for make=nissan (the site's own list) ===")
        slugs: list[str] = []
        for page in [f"{BASE}/used-cars.php?make=nissan", f"{BASE}/used-cars?make=nissan"]:
            resp = get(client, page)
            if resp is None or resp.status_code != 200:
                print(f"  {page}: HTTP {resp.status_code if resp else '-'}")
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            print(f"  {page}: HTTP 200")
            for sel in soup.find_all("select"):
                name = sel.get("name") or ""
                if "model" not in name.lower():
                    continue
                opts = [(o.get("value") or "").strip() for o in sel.find_all("option")]
                opts = [o for o in opts if o]
                print(f"    select {name!r}: {len(opts)} options")
                for o in opts:
                    print(f"      {o}")
                slugs.extend(opts)

        print("\n=== B. make index /nissan/ — model links and their slugs ===")
        resp = get(client, f"{BASE}/nissan/")
        if resp is not None:
            print(f"  HTTP {resp.status_code} {len(resp.text)}B")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = [(a.get_text(" ", strip=True)[:40], a["href"])
                         for a in soup.find_all("a", href=True)
                         if "/nissan/" in a["href"]]
                seen = set()
                for text, href in links:
                    key = href.split("?")[0]
                    if key in seen:
                        continue
                    seen.add(key)
                    print(f"    {text:<40} {href[:90]}")
                    if len(seen) > 60:
                        break

        print("\n=== C. current detail-URL shape from real cards ===")
        resp = get(client, f"{BASE}/used-cars.php?make=nissan")
        if resp is not None and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li.listItem")
            print(f"  li.listItem={len(cards)}")
            for card in cards[:4]:
                a = card.find("a", href=True)
                title = card.get_text(" ", strip=True)[:60]
                print(f"    {a['href'][:100] if a else '(no link)'}")
                print(f"        {title}")

        print("\n=== D. sitemap.xml contents ===")
        resp = get(client, f"{BASE}/sitemap.xml")
        if resp is not None and resp.status_code == 200:
            for loc in re.findall(r"<loc>([^<]+)</loc>", resp.text)[:40]:
                print(f"    {loc}")

        print("\n=== E. candidate slugs on both routes ===")
        candidates = ["datsun-truck", "datsun_truck", "datsuntruck", "datsun",
                      "datsun-pickup", "datsun-620", "sunny-truck", "truck"]
        # Anything the site's own dropdown offered that mentions datsun or a
        # truck wins a try too.
        candidates += [s for s in slugs
                       if re.search(r"datsun|truck|pickup", s, re.I)
                       and s not in candidates]
        for slug in candidates:
            for route in ["used-cars.php", "used-cars"]:
                url = f"{BASE}/{route}?make=nissan&model={slug}"
                resp = get(client, url)
                if resp is None:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li.listItem")
                marker = " <<<" if resp.status_code == 200 and cards else ""
                print(f"  {route:<14} model={slug:<16} HTTP {resp.status_code} "
                      f"cards={len(cards)}{marker}")
                if marker:
                    for card in cards[:6]:
                        a = card.find("a", href=True)
                        print(f"        {card.get_text(' ', strip=True)[:55]}")
                        print(f"          {a['href'][:95] if a else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
