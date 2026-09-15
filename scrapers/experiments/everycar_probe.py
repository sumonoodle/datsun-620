"""Probe: everycar.jp moved. Find where the Datsun Truck stock lives now.

The collector's search URL

    /used-cars.php?make=nissan&model=datsun-truck

has answered 404 for five consecutive daily runs. The detail-URL shape the
parser keys on (/nissan/<slug>/<year>/<id>/) may well be intact — only the
search entry point may have changed — so this probe looks for any route
that still lists Datsun Truck stock, and reports enough markup detail to
rewrite the collector in one pass.

Reports, per candidate: HTTP status, byte size, whether "datsun" appears,
how many li.listItem cards parse, and how many hrefs match the detail
pattern. Then dumps the homepage's search form and any Datsun links, plus
sitemap entries, so a route we did not guess still shows itself.

Scaffolding: delete once the collector is fixed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings.everycar import _DETAIL_RE, HEADERS, URL

BASE = "https://www.everycar.jp"

CANDIDATES = [
    URL,                                              # the one that 404s
    f"{BASE}/used-cars.php?make=nissan",              # drop the model facet
    f"{BASE}/used-cars.php",
    f"{BASE}/used-cars/nissan/datsun-truck",          # path-style facets
    f"{BASE}/used-cars/nissan/datsun-truck/",
    f"{BASE}/nissan/datsun-truck/",                   # detail-path prefix as index
    f"{BASE}/used-cars/nissan",
    f"{BASE}/stocklist.php?make=nissan&model=datsun-truck",
    f"{BASE}/search?make=nissan&model=datsun-truck",
    f"{BASE}/?s=datsun+truck",
    BASE,
]


def describe(client: httpx.Client, url: str) -> None:
    try:
        resp = client.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    except Exception as exc:
        print(f"  {url}\n      {type(exc).__name__}: {str(exc)[:110]}")
        return
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.listItem")
    details = _DETAIL_RE.findall(html)
    final = str(resp.url)
    print(f"  {url}")
    print(f"      HTTP {resp.status_code}  {len(html)}B  datsun={'datsun' in html.lower()}"
          f"  li.listItem={len(cards)}  detail_hrefs={len(details)}")
    if final != url:
        print(f"      redirected -> {final}")
    if details:
        for slug, year, ident in details[:8]:
            print(f"        detail: {slug} {year} {ident}")
    elif resp.status_code == 200 and "datsun" in html.lower():
        # The route works but our detail pattern does not match its links:
        # show what the Datsun links actually look like.
        for a in soup.find_all("a", href=True):
            if "datsun" in a["href"].lower():
                print(f"        datsun href: {a['href'][:100]}")
                break


def main() -> int:
    with httpx.Client() as client:
        print("=== A. candidate routes ===")
        for url in CANDIDATES:
            describe(client, url)

        print("\n=== B. homepage search form + Datsun links ===")
        try:
            resp = client.get(BASE, headers=HEADERS, timeout=30,
                              follow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")
            for form in soup.find_all("form")[:4]:
                names = [i.get("name") for i in form.find_all(["input", "select"])
                         if i.get("name")]
                print(f"  form action={form.get('action')!r} method={form.get('method')!r}")
                print(f"       fields={names[:14]}")
                # The make/model selects name the site's own slugs.
                for sel in form.find_all("select"):
                    opts = [o.get("value") for o in sel.find_all("option")
                            if o.get("value") and "datsun" in
                            (o.get("value", "") + o.get_text()).lower()]
                    if opts:
                        print(f"       select {sel.get('name')!r} datsun options: {opts[:6]}")
            hrefs = {a["href"] for a in soup.find_all("a", href=True)
                     if "datsun" in a["href"].lower()}
            print(f"  homepage datsun hrefs ({len(hrefs)}):")
            for h in list(hrefs)[:12]:
                print(f"      {h[:110]}")
            paths = sorted({re.sub(r"\d+", "N", a["href"].split("?")[0])
                            for a in soup.find_all("a", href=True)})
            print(f"  distinct homepage path shapes ({len(paths)}), first 25:")
            for p in paths[:25]:
                print(f"      {p[:100]}")
        except Exception as exc:
            print(f"  homepage failed: {type(exc).__name__}: {str(exc)[:110]}")

        print("\n=== C. sitemap ===")
        for sm in [f"{BASE}/sitemap.xml", f"{BASE}/sitemap_index.xml",
                   f"{BASE}/robots.txt"]:
            try:
                resp = client.get(sm, headers=HEADERS, timeout=30,
                                  follow_redirects=True)
                body = resp.text
                hits = re.findall(r"https?://[^\s<\"]*datsun[^\s<\"]*", body, re.I)
                print(f"  {sm}: HTTP {resp.status_code} {len(body)}B "
                      f"datsun_urls={len(hits)}")
                for h in hits[:10]:
                    print(f"      {h[:110]}")
                if sm.endswith("robots.txt"):
                    print("      " + " | ".join(body.split("\n")[:8]))
            except Exception as exc:
                print(f"  {sm}: {type(exc).__name__}: {str(exc)[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
