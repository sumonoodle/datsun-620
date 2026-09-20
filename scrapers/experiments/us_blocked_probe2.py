"""Probe round 2: is Hemmings' sitemap a usable door, and is there any
aggregator that is not also walled?

Round 1 split the two sources apart.

Cars & Bids is IP-banned outright: robots.txt answers 200, but the
HOMEPAGE itself 403s, as do the API, sitemap, search and past-auctions.
When the front door is challenged there is no clever endpoint left, and
the only honest route is their email alerts. Same for classic.com, which
would otherwise have covered both blocked sources at once.

Hemmings is different, and this round exists because of it: robots.txt
AND /sitemap.xml both return 200 with real content, while every dynamic
page is challenged. Static files are evidently served past the bot check.
The sitemap index names five sub-sitemaps, so the question is whether any
of them enumerates individual 620 listings.

What that would and would not buy us, stated before looking so the answer
is not talked up afterwards: a sitemap carries URLs and lastmod dates,
never prices or titles. The detail pages are 403, so a collector built on
this could report THAT a 620 is listed on Hemmings and link to it - the
owner's own browser is not blocked - but not what it costs. That is a
degraded record, and worth having only if the URLs really are per-listing
rather than per-search-page.

Also sweeps a few aggregators not yet tried, in case one carries Hemmings
or Cars & Bids inventory without the same wall.

robots.txt is checked and obeyed throughout. No evasion.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib import robotparser

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import hemmings as hem

HEADERS = {"User-Agent": hem.HEADERS["User-Agent"],
           "Accept-Language": "en-GB,en;q=0.9"}

_RE_620_WORD = re.compile(r"\b620\b")

SUB_SITEMAPS = [
    "https://www.hemmings.com/sitemap_main.xml",
    "https://www.hemmings.com/sitemap_kw.xml",
    "https://www.hemmings.com/sitemap_locales.xml",
    "https://www.hemmings.com/sitemap_metros.xml",
    "https://www.hemmings.com/sitemap_makes.xml",
]

# Aggregators that carry other sites' classified inventory.
AGGREGATORS = [
    ("autotempest",     "https://www.autotempest.com/robots.txt",
                        "https://www.autotempest.com/results?make=datsun&model=620"),
    ("oldcaronline",    "https://www.oldcaronline.com/robots.txt",
                        "https://www.oldcaronline.com/search?q=datsun+620"),
    ("classiccarsforsale", "https://www.classiccarsforsale.co.uk/robots.txt",
                        "https://www.classiccarsforsale.co.uk/datsun/620"),
    ("smartmotorguide", "https://www.smartmotorguide.com/robots.txt",
                        "https://www.smartmotorguide.com/search?q=datsun+620"),
]


def get(client, url, accept="*/*"):
    try:
        return client.get(url, headers={**HEADERS, "Accept": accept},
                          timeout=30, follow_redirects=True), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:90]}"


def challenged(body: str) -> bool:
    low = body[:4000].lower()
    return any(w in low for w in ("captcha", "are you a human", "access denied",
                                  "just a moment", "cloudflare", "perimeterx",
                                  "datadome", "blocked"))


def main() -> int:
    with httpx.Client() as client:
        print("=== A. Hemmings sub-sitemaps: do they list individual ads? ===",
              flush=True)
        for url in SUB_SITEMAPS:
            resp, err = get(client, url, "application/xml")
            if err:
                print(f"  {url.rsplit('/', 1)[-1]:<24} {err}", flush=True)
                continue
            body = resp.text
            name = url.rsplit("/", 1)[-1]
            if resp.status_code != 200:
                print(f"  {name:<24} HTTP {resp.status_code} "
                      f"{'CHALLENGE' if challenged(body) else ''}", flush=True)
                continue
            locs = re.findall(r"<loc>([^<]+)</loc>", body)
            # A per-LISTING url ends in a numeric id; a per-SEARCH url does not.
            listing_like = [l for l in locs if re.search(r"/\d{5,}/?$", l)]
            datsun = [l for l in locs if "datsun" in l.lower()]
            six20 = [l for l in datsun if re.search(r"/620\b|620", l)]
            print(f"  {name:<24} HTTP 200 {len(body):>9}B locs={len(locs)} "
                  f"listing-like={len(listing_like)} datsun={len(datsun)} "
                  f"620={len(six20)}", flush=True)
            for sample in (six20 or datsun or locs)[:5]:
                print(f"        {sample[:110]}", flush=True)
            # Nested sitemap index? Follow one level for the makes file.
            nested = re.findall(r"<loc>([^<]*sitemap[^<]*)</loc>", body)
            if nested and name == "sitemap_makes.xml":
                for n in nested[:3]:
                    r2, e2 = get(client, n, "application/xml")
                    if e2 or r2.status_code != 200:
                        print(f"        nested {n[:70]}: "
                              f"{e2 or ('HTTP ' + str(r2.status_code))}", flush=True)
                        continue
                    l2 = re.findall(r"<loc>([^<]+)</loc>", r2.text)
                    d2 = [x for x in l2 if "datsun" in x.lower()]
                    print(f"        nested {n[:60]}: locs={len(l2)} "
                          f"datsun={len(d2)}", flush=True)
                    for s in d2[:4]:
                        print(f"            {s[:100]}", flush=True)

        print("\n=== B. does a Hemmings DETAIL page answer, or only static? ===",
              flush=True)
        # If detail pages were reachable, the sitemap would be a full route.
        for url in ["https://www.hemmings.com/classifieds/cars-for-sale/datsun/620",
                    "https://www.hemmings.com/sitemap.xml"]:
            resp, err = get(client, url)
            state = err or (f"HTTP {resp.status_code}"
                            + (" CHALLENGE" if challenged(resp.text) else ""))
            print(f"  {url[:70]:<72} {state}", flush=True)

        print("\n=== C. other aggregators, robots first ===", flush=True)
        for name, robots_url, search_url in AGGREGATORS:
            rresp, rerr = get(client, robots_url, "text/plain")
            if rerr or rresp.status_code != 200:
                print(f"  {name:<22} robots: {rerr or rresp.status_code}",
                      flush=True)
                allowed = None
            else:
                parser = robotparser.RobotFileParser()
                parser.parse(rresp.text.split("\n"))
                allowed = parser.can_fetch("*", search_url)
                print(f"  {name:<22} robots 200, search path "
                      f"{'ALLOWED' if allowed else 'DISALLOWED'}", flush=True)
            if allowed is False:
                print(f"  {'':<22} -> not probed further, robots says no",
                      flush=True)
                continue
            sresp, serr = get(client, search_url, "text/html")
            if serr:
                print(f"  {'':<22} search: {serr}", flush=True)
                continue
            body = sresp.text
            has_620 = bool(_RE_620_WORD.search(body))
            print(f"  {'':<22} search HTTP {sresp.status_code} {len(body)}B "
                  f"{'CHALLENGE' if challenged(body) else ''} "
                  f"datsun={'datsun' in body.lower()} "
                  f"620={has_620}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
