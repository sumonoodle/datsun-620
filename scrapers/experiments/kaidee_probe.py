"""Probe: where does Kaidee keep its ad data now?

The collector has failed two days with "__NEXT_DATA__ missing (page layout
changed or blocked?)". That string is the Next.js PAGES-router payload, so
the likeliest explanation is a migration to the App Router, which streams
data as self.__next_f RSC chunks instead. A block is the other
possibility, and the two look nothing alike, so check before assuming.

Note the collector failed LOUDLY rather than returning zero - the
degradable pattern working as intended, which is why this is a two-day
problem and not a two-month one.

Questions, in order:
  A. Does the page even answer, and does robots still allow it?
  B. Which framework payload is present now: __NEXT_DATA__, __next_f,
     ld+json, or server-rendered cards?
  C. If the data streams as RSC chunks, is a recognisable ad object in
     there (id, title, price) that can be parsed as reliably as the old
     pageProps.ads array?
  D. Is there a plain JSON API behind the search that would be a better
     target than either?

Scaffolding: delete once the collector is fixed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib import robotparser
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import kaidee as kd

SEARCH = kd.SEARCH_URL.format(quote("datsun"))
API_CANDIDATES = [
    "https://rod.kaidee.com/api/search?q=datsun",
    "https://api.kaidee.com/v1/search?q=datsun",
    "https://rod.kaidee.com/_next/data/search.json?q=datsun",
]


def get(client, url, accept="*/*"):
    try:
        return client.get(url, headers={**kd.HEADERS, "Accept": accept},
                          timeout=40, follow_redirects=True), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def main() -> int:
    with httpx.Client() as client:
        print("=== A. reachable, and permitted? ===", flush=True)
        r, err = get(client, f"{kd.BASE}/robots.txt", "text/plain")
        if err or r.status_code != 200:
            print(f"  robots: {err or r.status_code} (treat as unknown)", flush=True)
        else:
            p = robotparser.RobotFileParser()
            p.parse(r.text.split("\n"))
            print(f"  robots 200; search path allowed: "
                  f"{p.can_fetch('*', SEARCH)}", flush=True)

        resp, err = get(client, SEARCH, "text/html")
        if err:
            print(f"  search: {err}", flush=True)
            return 0
        html = resp.text
        low = html.lower()
        challenge = any(w in low[:6000] for w in
                        ("captcha", "are you a human", "access denied",
                         "just a moment", "cloudflare", "datadome"))
        print(f"  search HTTP {resp.status_code} {len(html)}B "
              f"challenge={challenge}", flush=True)
        if resp.status_code != 200:
            print("  -> not a layout change, a block. Stop here.", flush=True)
            return 0

        print("\n=== B. which payload does it ship? ===", flush=True)
        markers = {
            "__NEXT_DATA__ (old pages router)": "__NEXT_DATA__",
            "self.__next_f (app router RSC)": "self.__next_f",
            "__NUXT__": "__NUXT__",
            "window.__INITIAL": "window.__INITIAL",
            "application/ld+json": "application/ld+json",
            "apollo state": "__APOLLO_STATE__",
        }
        for label, needle in markers.items():
            print(f"  {label:<36} {needle in html}", flush=True)

        soup = BeautifulSoup(html, "html.parser")
        prod_links = soup.select("a[href*='/product-']")
        print(f"  a[href*='/product-'] count: {len(prod_links)}", flush=True)
        for a in prod_links[:6]:
            print(f"      {a.get('href')[:70]} :: "
                  f"{a.get_text(' ', strip=True)[:50]!r}", flush=True)
        for sel in ["[data-testid]", "article", "li a[href*='product']"]:
            print(f"  {sel:<24} {len(soup.select(sel))}", flush=True)

        print("\n=== C. RSC chunks: is an ad object in there? ===", flush=True)
        # App-router pages push escaped JSON fragments; the ad fields we need
        # would still appear as keys even inside an escaped blob.
        for key in ['\\"title\\"', '\\"price\\"', '"title"', '"price"',
                    '\\"legacyId\\"', '\\"adId\\"', 'ช้างเหยียบ', 'datsun']:
            print(f"  contains {key!r:<20} {key in html}", flush=True)
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
        print(f"  __next_f chunks: {len(chunks)}", flush=True)
        if chunks:
            joined = "".join(chunks)
            print(f"  joined chunk payload: {len(joined)}B", flush=True)
            # Where do the ad-looking fields sit in that payload?
            for m in list(re.finditer(r'\\"(?:title|price|id)\\":', joined))[:3]:
                s = max(0, m.start() - 120)
                print(f"      ...{joined[s:m.start() + 260]}...", flush=True)

        print("\n=== D. any plain JSON API? ===", flush=True)
        for url in API_CANDIDATES:
            r2, e2 = get(client, url, "application/json")
            if e2:
                print(f"  {url[:58]:<60} {e2}", flush=True)
                continue
            body = r2.text
            looks_json = body.strip()[:1] in "{["
            print(f"  {url[:58]:<60} HTTP {r2.status_code} {len(body)}B "
                  f"json={looks_json}", flush=True)
            if r2.status_code == 200 and looks_json:
                try:
                    data = json.loads(body)
                    if isinstance(data, dict):
                        print(f"      keys: {list(data)[:12]}", flush=True)
                except Exception as exc:
                    print(f"      unparseable: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
