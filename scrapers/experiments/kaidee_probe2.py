"""Probe round 2: what IS Kaidee's 5KB shell, and where is the real data?

Round 1 was strange in a useful way. The search page answers HTTP 200 with
no challenge text — but only 5,077 bytes, with no __NEXT_DATA__, no
__next_f, no ld+json, no product links, and not even the word "datsun" in
the body. And /api/search and /_next/data/search.json return the SAME
5,077 bytes, which means those are not endpoints at all: everything is
falling through to one catch-all response.

Two readings, and they lead opposite ways:
  1. Kaidee became a client-rendered SPA. The shell is real, a browser
     boots it and fetches ads by XHR, and there IS an API - round 1 simply
     guessed the wrong URLs. Finding it fixes the collector.
  2. It is a soft block: datacentre IPs get a stub with no challenge page,
     while browsers get the full thing. Then Kaidee is lost from runners,
     like Cars & Bids, and the honest answer is the alert route.

The shell is 5KB, so the cheapest way to tell them apart is to read it.
A real SPA shell carries a mount point and bundle scripts; a stub carries
neither. If bundles exist, they name the API base URL in plain text, so
this fetches one and greps it.

Also checks the sitemap: if it enumerates product URLs, those are at least
links even without prices.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import kaidee as kd

SEARCH = kd.SEARCH_URL.format(quote("datsun"))


def get(client, url, accept="*/*"):
    try:
        return client.get(url, headers={**kd.HEADERS, "Accept": accept},
                          timeout=40, follow_redirects=True), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def main() -> int:
    with httpx.Client() as client:
        print("=== A. the shell, in full ===", flush=True)
        resp, err = get(client, SEARCH, "text/html")
        if err:
            print(f"  {err}", flush=True)
            return 0
        html = resp.text
        print(f"  HTTP {resp.status_code}  {len(html)}B  "
              f"final={str(resp.url)[:90]}", flush=True)
        print("  --- body begins ---", flush=True)
        for line in html.splitlines():
            line = line.rstrip()
            if line.strip():
                print(f"  {line[:200]}", flush=True)
        print("  --- body ends ---", flush=True)

        print("\n=== B. bundles: do they name an API? ===", flush=True)
        soup = BeautifulSoup(html, "html.parser")
        srcs = [s.get("src") for s in soup.find_all("script", src=True)]
        print(f"  script src count: {len(srcs)}", flush=True)
        for s in srcs[:10]:
            print(f"      {s[:110]}", flush=True)
        # Fetch the first couple and look for API hosts/paths in plain text.
        api_pat = re.compile(
            r"https://[a-z0-9.\-]*kaidee\.com/[A-Za-z0-9/_\-.]*"
            r"|/api/[A-Za-z0-9/_\-.]+|graphql", re.I)
        for s in srcs[:3]:
            url = urljoin(str(resp.url), s)
            r2, e2 = get(client, url, "application/javascript")
            if e2 or r2.status_code != 200:
                print(f"  {url[:70]}: {e2 or r2.status_code}", flush=True)
                continue
            hits = sorted(set(api_pat.findall(r2.text)))
            print(f"  {url[:70]}: {len(r2.text)}B, {len(hits)} api-like strings",
                  flush=True)
            for h in hits[:15]:
                print(f"      {h[:100]}", flush=True)

        print("\n=== C. sitemap: are product URLs listed? ===", flush=True)
        for sm in [f"{kd.BASE}/sitemap.xml", f"{kd.BASE}/robots.txt"]:
            r3, e3 = get(client, sm, "application/xml")
            if e3:
                print(f"  {sm}: {e3}", flush=True)
                continue
            body = r3.text
            print(f"  {sm}: HTTP {r3.status_code} {len(body)}B", flush=True)
            if sm.endswith("robots.txt"):
                for line in body.splitlines()[:12]:
                    if line.strip():
                        print(f"      {line[:100]}", flush=True)
                continue
            locs = re.findall(r"<loc>([^<]+)</loc>", body)
            prods = [l for l in locs if "product-" in l]
            print(f"      locs={len(locs)} product-urls={len(prods)}", flush=True)
            for l in (prods or locs)[:6]:
                print(f"      {l[:100]}", flush=True)

        print("\n=== D. control: does the site root differ from the shell? ===",
              flush=True)
        r4, e4 = get(client, kd.BASE, "text/html")
        if not e4:
            same = r4.text == html
            print(f"  root HTTP {r4.status_code} {len(r4.text)}B "
                  f"identical-to-search-page={same}", flush=True)
            print("  (identical root and search page means one catch-all "
                  "response, i.e. a stub, not an SPA)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
