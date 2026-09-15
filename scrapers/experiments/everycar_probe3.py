"""Probe round 3: is everycar's 404 "site changed" or "no stock today"?

Round 2 showed the detail-URL shape is intact
(/nissan/ud-truck/2012/7958102/ — exactly what the parser keys on) and
that sibling slugs are formed just like ours: ud-truck, vanette-truck.
That makes "the site renamed datsun-truck" unlikely, and raises a very
different possibility: everycar 404s a model facet that currently has NO
STOCK, so our 404 means "no Datsun Truck in inventory right now" rather
than "collector broken".

That distinction decides the fix, so ask three narrow questions:
  A. Does the Nissan model dropdown list a datsun slug at all? (It is
     the site's own list, and if it only lists models in stock, ours
     will be absent while a stocked one like ud-truck is present.)
  B. Is Datsun its own make now (make=datsun, /datsun/)?
  C. What does the 404 body actually SAY — "not found" or "no results"?

Prints a few lines only. Scaffolding: delete once the collector is fixed.
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


def dropdown(soup, name_match):
    for sel in soup.find_all("select"):
        if name_match in (sel.get("name") or "").lower():
            return [((o.get("value") or "").strip(),
                     o.get_text(" ", strip=True)[:40])
                    for o in sel.find_all("option") if (o.get("value") or "").strip()]
    return []


def main() -> int:
    with httpx.Client() as client:
        print("=== A. Nissan model dropdown (the site's own valid slugs) ===")
        resp = get(client, f"{BASE}/used-cars?make=nissan")
        if resp is not None and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            models = dropdown(soup, "model")
            print(f"  {len(models)} model options for make=nissan")
            hits = [m for m in models if "datsun" in (m[0] + m[1]).lower()]
            print(f"  datsun options: {hits if hits else 'NONE'}")
            print("  all slugs:")
            print("   " + ", ".join(v for v, _ in models))

            makes = dropdown(soup, "make")
            mhits = [m for m in makes if "datsun" in (m[0] + m[1]).lower()]
            print(f"  make options: {len(makes)}; datsun among them: "
                  f"{mhits if mhits else 'NONE'}")

        print("\n=== B. Datsun as its own make ===")
        for url in [f"{BASE}/used-cars?make=datsun",
                    f"{BASE}/used-cars.php?make=datsun",
                    f"{BASE}/datsun/",
                    f"{BASE}/nissan/datsun-truck/1978/",
                    ]:
            resp = get(client, url)
            if resp is None:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li.listItem")
            detail = re.findall(r"everycar\.jp/[a-z]+/(datsun[a-z0-9-]*)/", resp.text)
            print(f"  {url}\n      HTTP {resp.status_code} cards={len(cards)} "
                  f"datsun_detail_slugs={sorted(set(detail))[:6]}")
            for card in cards[:5]:
                print(f"        {card.get_text(' ', strip=True)[:60]}")

        print("\n=== C. what the 404 body says ===")
        resp = get(client, f"{BASE}/used-cars.php?make=nissan&model=datsun-truck")
        if resp is not None:
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else "(no title)"
            print(f"  HTTP {resp.status_code}  <title>{title[:90]}")
            # The first few visible headings/paragraphs say which it is.
            for tag in soup.find_all(["h1", "h2", "h3", "p"])[:10]:
                text = tag.get_text(" ", strip=True)
                if text:
                    print(f"    {tag.name}: {text[:100]}")

        print("\n=== D. control: a slug known to have stock ===")
        resp = get(client, f"{BASE}/used-cars.php?make=nissan&model=ud-truck")
        print(f"  ud-truck -> HTTP {resp.status_code if resp else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
